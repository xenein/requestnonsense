#!/usr/bin/env python3
"""
so, requests are NamedTuples.
like so (waiting: bool, non_prio: bool, timestamp: float, song: str, requestee: str)
waiting is opposite of current, non_prio <-> prio
we put them in a glorified list. why?
we can use .sort() and get it nicely ordered
we put a class around it, so we can sneak sqlite in

what else?
everyone in chat can request
you can have one request in queue
if you send another, you keep your place in the queue, song is changed though

the list of available songs as well as the current queue are pushed to hackmd-notes
"""

from decouple import config, Csv
from twitchio.ext import commands
from typing import NamedTuple, TypedDict

import csv
import pickle
import random
import requests
import time
import os

# config
HackMDConfig = TypedDict(
    "HackMDConfig",
    {
        "tags": str,
        "headers": dict[str, str],
        "endpoint": str,
        "payload": dict[str, str],
        "queueTitle": str,
        "listTitle": str,
    },
)
HACKMD_CONFIG = HackMDConfig(
    tags=f"---\ntags: {config('HACKMDTAG', default='requestnonsense')}\n---",
    headers={"Authorization": f"Bearer {config('HACKMDTOKEN')}"},
    endpoint="https://api.hackmd.io/v1/notes/",
    payload={
        "readPermission": "guest",
        "writePermission": "owner",
        "commentPermission": "disabled",
    },
    queueTitle=str(config("QUEUETITLE", default="Queue")),
    listTitle=str(config("LISTTITLE", default="List")),
)


ListConfig = TypedDict(
    "ListConfig", {"delimiter": str, "CFSM": bool, "instruments": list, "path": str}
)
LIST_CONFIG = ListConfig(
    delimiter=str(config("LIST_DELIMITER", default=";")),
    CFSM=bool(config("LIST_CFSM", cast=bool)),
    instruments=config("INSTRUMENTS", cast=Csv(), default=[]),  # type: ignore
    path=str(config("SONGLIST", default="./songlist.csv")),
)


# request-tuples
class RequestTuple(NamedTuple):
    """Requests are handled in tuples. Fields within requests can be accessed by name, too"""

    waiting: bool
    non_prio: bool
    timestamp: float
    song: str
    requestee: str


class RequestQueue:
    """wir machen jetzt alberne Tricks, um die Queue irgendwann in sqlite zu haben. yay"""

    data: list[RequestTuple]
    url: str

    def __init__(self):
        self.url = create_note("")
        if os.path.exists(config("QUEUE_FILE")):
            with open(config("QUEUE_FILE"), mode="rb") as fh:
                self.data = pickle.load(fh)
        else:
            self.data = list()
        update_note(self.generate_requests_markdown(), self.url)

    def append(self, item: RequestTuple):
        self.data.append(item)

    def insert(self, position: int, item: RequestTuple):
        self.data.insert(position, item)

    def remove(self, item: RequestTuple):
        self.data.remove(item)

    def get_first(self) -> RequestTuple:
        return self.get_element(0)

    def get_element(self, idx: int) -> RequestTuple:
        return self.data[idx]

    def get_random(self) -> RequestTuple:
        return random.choice(self.data)

    def sort(self):
        self.data.sort()

    def len(self) -> int:
        return len(self.data)

    def get_index_for_user(self, user: str) -> int | None:
        for idx, entry in enumerate(self.data, start=1):
            if entry.requestee == user:
                return idx
        return None

    def get_request_for_user(self, user: str) -> RequestTuple | None:
        for entry in self.data:
            if entry.requestee == user:
                return entry
        return None

    def safe_queue(self):
        with open(config("QUEUE_FILE"), mode="wb") as fh:
            pickle.dump(self.data, fh)
        update_note(self.generate_requests_markdown(), self.url)

    def generate_requests_markdown(self) -> str:
        if len(self.data) == 0:
            return f"{HACKMD_CONFIG.get('tags')}# {HACKMD_CONFIG.get('queueTitle')}\n Beeindruckend leer hier"
        requests_markdown = [
            f"{HACKMD_CONFIG.get('tags')}# {HACKMD_CONFIG.get('queueTitle')}",
            "",
            "| Pos | Song | User |",
            "| --- | --- | --- |",
        ]
        for idx, request in enumerate(self.data, start=1):
            requests_markdown.append(
                f"| {idx} | {request.song} | {request.requestee} |"
            )

        return "\n".join(requests_markdown)

    def process_request(self, song: str, requestee: str) -> str:
        waiting = True
        non_prio = True
        moment = time.time()

        if (request := self.get_request_for_user(requestee)) is not None:
            request_tuple = RequestTuple(
                request.waiting,
                request.non_prio,
                request.timestamp,
                song,
                requestee,
            )
            self.append(request_tuple)
            self.remove(request)
            self.sort()
            message = f"@{requestee}: Dein Request wurde aktualisert zu {song}"
        else:
            request_tuple = RequestTuple(waiting, non_prio, moment, song, requestee)
            self.append(request_tuple)
            message = f"@{requestee}: Dein Request für {song} ist eingetragen."

        self.safe_queue()
        return message

    def process_upgrade(self, requestee: str, author: str) -> str:
        if (request := self.get_request_for_user(requestee)) is not None:
            self.remove(request)
            self.append(
                RequestTuple(
                    request.waiting,
                    False,
                    request.timestamp,
                    request.song,
                    request.requestee,
                )
            )
            self.sort()
            self.safe_queue()
            print(f"Der Request von {request.requestee} hat jetzt prio")
            message = f"@{author}: Der Request von {request.requestee} hat jetzt prio"
        else:
            print(f"{requestee} hat keine Request in der Warteschlange")
            message = f"@{author}: {requestee} hat keine Request in der Warteschlange"
        return message

    def advance_queue(self, next_song: RequestTuple) -> str:
        if len(self.data) > 0:
            top_song = self.get_first()
            if not top_song.waiting:
                # [0] is waiting -> not waiting -> song was active
                self.remove(top_song)

            self.remove(next_song)
            self.append(
                RequestTuple(
                    False,
                    next_song.non_prio,
                    next_song.timestamp,
                    next_song.song,
                    next_song.requestee,
                )
            )
            self.sort()
            message = (
                f"Nächster Song: {next_song.song} requestet von {next_song.requestee}"
            )
            self.safe_queue()
        else:
            message = "Queue leer, säd"
        print(message)

        return message


def create_note(content: str) -> str:
    payload = {
        "content": content,
    }
    payload.update(HACKMD_CONFIG.get("payload"))

    _response = requests.post(
        HACKMD_CONFIG.get("endpoint"),
        headers=HACKMD_CONFIG.get("headers"),
        json=payload,
    )
    return f"https://hackmd.io/{_response.json().get('id')}"


def update_note(content: str, note_url: str) -> bool:
    note_id = note_url.split("/")[-1]
    payload = {
        "content": content,
    }
    payload.update(HACKMD_CONFIG.get("payload"))

    _response = requests.patch(
        f"{HACKMD_CONFIG.get('endpoint')}{note_id}",
        headers=HACKMD_CONFIG.get("headers"),
        json=payload,
    )

    return _response.status_code == 202


songs = dict()
songs_url = ""
if os.path.exists(LIST_CONFIG.get("path")):
    with open(LIST_CONFIG.get("path")) as fh:
        start = 1 if LIST_CONFIG.get("CFSM") else 0
        csv_lines = fh.readlines()[start:]
    reader = csv.DictReader(csv_lines, delimiter=LIST_CONFIG.get("delimiter"))

    song_set = set()
    for line in reader:
        if instruments := LIST_CONFIG.get("instruments"):
            for instrument in instruments:
                if instrument in str(line.get("Arrangements")):
                    song_set.add((line.get("Artist"), line.get("Title")))
        else:
            song_set.add((line.get("Artist"), line.get("Title")))

    song_list = list(song_set)
    song_list.sort()
    for idx, song in enumerate(song_list, start=1):
        songs[idx] = f"{song[0]} - {song[1]}"

    songlist_markdown = [
        HACKMD_CONFIG.get("tags"),
        f"""# {HACKMD_CONFIG.get("listTitle")}

Such dir einen Song raus, kopier das Request-Command und fügs im Chat ein.



| Artist | Title | Command&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; |
| --- | --- | --- |""",
    ]
    for idx, song in enumerate(song_list, start=1):
        songlist_markdown.append(f"| {song[0]} | {song[1]} | ?request {idx} |")

    songs_url = create_note("\n".join(songlist_markdown))


class Bot(commands.Bot):
    message_prefix: str = ""
    queue: RequestQueue

    def __init__(self):
        super().__init__(
            token=str(config("ACCESS_TOKEN")),
            prefix=config("BOT_PREFIX", cast=Csv(post_process=list), default="?,!"),  # type: ignore
            initial_channels=[config("CHANNEL")],
        )
        self.message_prefix = str(config("MESSAGE_PREFIX"))
        self.queue = RequestQueue()

    async def send_message(self, ctx: commands.Context, message: str):
        if self.message_prefix:
            await ctx.send(f"{self.message_prefix}: {message}")
        else:
            await ctx.send(message)

    async def event_ready(self):
        print(f"Logged in as: {self.nick}")
        print(f"User id: {self.user_id}")
        await self.connected_channels[0].send("Requestnonsense bereit")

    @commands.command()
    async def meow(self, ctx: commands.Context):
        print("meow awaited")
        await self.send_message(ctx, "meow!")

    @commands.command()
    async def request(self, ctx: commands.Context):
        """
        request command: add song as non prio, non current request to the end of queue OR
        change song data in the request for a given user
        """
        print("request awaited")
        cmd_message = str(ctx.message.content)
        cmd_arg = cmd_message.split(" ", maxsplit=1)[1]
        song = songs.get(int(cmd_arg))
        requestee = str(ctx.author.name)
        message: str
        if song:
            message = self.queue.process_request(song, requestee)
        else:
            print(f"song {song} not found")
            message = f"@{ctx.author.name} konnte keinen Song für {ctx.message} finden"
        print(message)
        await self.send_message(ctx, message)

    @commands.command()
    async def upgrade_request(self, ctx: commands.Context):
        message: str
        if ctx.author.is_mod:
            print("upgrade awaited")
            command = str(ctx.message.content)
            author = str(ctx.author.name)
            requestee = command.split(" ", maxsplit=1)[1]
            if requestee.startswith("@"):
                requestee = requestee[1:]
            message = self.queue.process_upgrade(requestee, author)
        else:
            message = f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl"
        await self.send_message(ctx, message)

    @commands.command()
    async def position(self, ctx: commands.Context):
        if (
            idx := self.queue.get_index_for_user(str(ctx.message.author.name))
        ) is not None:
            message = f"Dein Request {self.queue.get_element(idx-1).song} ist aktuell auf Platz {idx} in der Warteschlange"
        else:
            message = "Du hast anscheinend gar keinen Song in der Warteschlange"
        await self.send_message(ctx, f"@{ctx.message.author.name}: {message}")

    @commands.command()
    async def next(self, ctx: commands.Context):
        message: str
        next_song: RequestTuple = self.queue.get_first()
        for request in self.queue.data:
            if request.waiting:
                next_song = request
                break

        if ctx.author.is_mod:
            message = self.queue.advance_queue(next_song)
        else:
            message = f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl"

        print(message)
        await self.send_message(ctx, message)

    @commands.command()
    async def randomize(self, ctx: commands.Context):
        message: str
        if ctx.author.is_mod:
            length = self.queue.len()
            if length == 0:
                return

            new_top = self.queue.get_random()
            message = self.queue.advance_queue(new_top)

        else:
            message = f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl"

        print(message)
        await self.send_message(ctx, message)

    @commands.command()
    async def scam(self, ctx: commands.Context):
        print("Scam awaited")
        cmd_message = str(ctx.message.content)
        cmd_arg = cmd_message.split(" ", maxsplit=1)[1]

        try:
            idx = int(cmd_arg)
        except ValueError:
            print(f"{cmd_arg} nach int casten nicht so die Idee.")
            await self.send_message(ctx, f"{cmd_arg} ist anscheinend keine Zahl")
            return

        length = self.queue.len()
        if idx >= length:
            await self.send_message(
                ctx, f"@{ctx.author.name}: So lang ist Queue nicht. Upsi"
            )
            return
        new_top = self.queue.get_element(idx - 1)

        if ctx.author.is_mod:
            message = self.queue.advance_queue(new_top)
        else:
            message = f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl"

        await self.send_message(ctx, message)

    @commands.command()
    async def help(self, ctx: commands.Context):
        await self.send_message(
            ctx,
            f"1: Song unter {songs_url} finden. "
            "2: Request-Befehl kopieren. "
            "3: Request-Befehl im Chat einfügen.",
        )

    @commands.command()
    async def rules(self, ctx: commands.Context):
        await self.send_message(
            ctx,
            "1: Request kostet nichts. "
            "2: 2 verschenkter Subs: wir schieben deinen Request hoch. "
            "3. Iron Maiden und Dragonforce nur für eine Dono für Kora von Mindestens 25 €.",
        )

    @commands.command()
    async def allrequests(self, ctx: commands.Context):
        await self.send_message(
            ctx, f"die gesamte Warteschlange gibts unter {self.queue.url}"
        )


if __name__ == "__main__":
    bot = Bot()
    bot.run()
