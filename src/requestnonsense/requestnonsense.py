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

from twitchio.ext import commands
from typing import NamedTuple

import csv
import pickle
import random
import requests
import time
import tomllib
import os


class HackMDNote:
    note_id: str
    content: str
    endpoint: str
    request_headers: dict

    def __init__(
        self,
        initial_content: str,
        api_token: str,
        endpoint: str = "https://api.hackmd.io/v1/notes/",
    ):
        self.content = initial_content
        self.request_headers = {"Authorization": f"Bearer {api_token}"}
        self.endpoint = endpoint

        payload = {
            "content": initial_content,
            "readPermission": "guest",
            "writePermission": "owner",
            "commentPermission": "disabled",
        }

        response = requests.post(
            self.endpoint, headers=self.request_headers, json=payload
        )
        self.id = response.json().get("id")

    def update(self, content: str) -> bool:
        self.content = content
        payload = {
            "content": content,
            "readPermission": "guest",
            "writePermission": "owner",
            "commentPermission": "disabled",
        }

        response = requests.patch(
            f"{self.endpoint}{self.id}", headers=self.request_headers, json=payload
        )

        return response.status_code == 302

    @property
    def url(self):
        return f"https://hackmd.io/{self.id}"


# request-tuples
class RequestTuple(NamedTuple):
    """Requests are handled in tuples. Fields within requests can be accessed by name, too"""

    waiting: bool
    non_prio: bool
    timestamp: float
    song: str
    requestee: str

    def __str__(self):
        return f"{self.song} requested von {self.requestee}"

    def __repr__(self):
        return f"<RequestTuple({self.waiting}, {self.non_prio}, {self.timestamp}, {self.song}, {self.requestee})>"


class RequestQueue:
    """wir machen jetzt alberne Tricks, um die Queue irgendwann in sqlite zu haben. yay"""

    data: list[RequestTuple]
    note: HackMDNote
    hackmd_tags: str
    queue_path: str
    queue_title: str

    def __init__(
        self,
        path: str,
        hackmd_token: str,
        hackmd_tags: str = "requestnonsense",
        hackmd_queue_title: str = "Queue",
        hackmd_endpoint: str = "https://api.hackmd.io/v1/notes/",
    ):
        self.hackmd_tags = hackmd_tags
        self.queue_title = hackmd_queue_title

        self.queue_path = path
        if os.path.exists(self.queue_path):
            with open(self.queue_path, mode="rb") as fh:
                self.data = pickle.load(fh)
        else:
            self.data = list()
        self.note = HackMDNote(
            self.generate_requests_markdown(),
            api_token=hackmd_token,
            endpoint=hackmd_endpoint,
        )

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
        with open(self.queue_path, mode="wb") as fh:
            pickle.dump(self.data, fh)
        self.note.update(self.generate_requests_markdown())

    def generate_requests_markdown(self) -> str:
        if len(self.data) == 0:
            return f"---\ntags: {self.hackmd_tags}\n---# {self.queue_title}\n Beeindruckend leer hier"
        requests_markdown = [
            f"---\ntags: {self.hackmd_tags}\n---# {self.queue_title}",
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
            message = f"@{requestee}: Dein Request wurde aktualisiert zu {song}"
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
                if len(self.data) == 0:
                    # no more songs left, säd
                    message = "Queue leer, säd"
                    print(message)
                    self.safe_queue()
                    return message
            if next_song not in self.data:
                message = f"{next_song.song} is nicht (mehr) in der Queue. Upsi."
                print(message)
                self.safe_queue()
                return message

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


class Songs(dict):
    note: HackMDNote
    csvpath: str
    markdown_start: list

    def __init__(
        self,
        csv_path: str,
        hackmd_token: str,
        bot_prefix: str,
        cfsm: bool = False,
        delimiter: str = ";",
        hackmd_tags: str = "requestnonsense",
        list_title: str = "List",
        instruments: list[str] = [],
    ):
        self.markdown_start = [
            f"---\ntags: {hackmd_tags}\n---",
            "\n {% hackmd theme-dark %} \n",
            f"""# {list_title}

Such dir einen Song raus, kopier das Request-Command und fügs im Chat ein.



| Artist | Title | Command&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; |
| --- | --- | --- |""",
        ]

        self.csvpath = csv_path
        if os.path.exists(self.csvpath):
            with open(self.csvpath) as fh:
                start = 1 if cfsm else 0
                csv_lines = fh.readlines()[start:]
            reader = csv.DictReader(csv_lines, delimiter=delimiter)

            # use set to ensure uniqueness and prevent nonsense
            song_set = set()
            for line in reader:
                if len(instruments) != 0:
                    for instrument in instruments:
                        if instrument in line["Arrangements"]:
                            song_set.add((line.get("Artist"), line.get("Title")))
                else:
                    song_set.add((line.get("Artist"), line.get("Title")))

            markdown = self.markdown_start[:]
            for idx, song in enumerate(sorted(song_set), start=1):
                self[idx] = f"{song[0]} - {song[1]}"
                markdown.append(
                    f"| {song[0]} | {song[1]} | {bot_prefix}request {idx} |"
                )

            self.note = HackMDNote("\n".join(markdown), api_token=hackmd_token)
            print(f"Songlist ready, see {self.note.url}")

    @property
    def url(self):
        return self.note.url


class Bot(commands.Bot):
    message_prefix: str
    queue: RequestQueue
    songs: Songs

    def __init__(
        self,
        csv_path: str,
        hackmd_token: str,
        hackmd_tags: str,
        queue_path: str,
        twitch_token: str,
        bot_prefix: list,
        channel: str,
        cfsm: bool,
        delimiter: str = ";",
        list_title: str = "List",
        queue_title: str = "Queue",
        message_prefix: str = "",
        instruments: list[str] = [],
    ):
        super().__init__(
            token=twitch_token,
            prefix=bot_prefix,
            initial_channels=[channel],
        )
        self.message_prefix = message_prefix

        self.songs = Songs(
            csv_path=csv_path,
            hackmd_token=hackmd_token,
            bot_prefix=bot_prefix[0],
            cfsm=cfsm,
            delimiter=delimiter,
            hackmd_tags=hackmd_tags,
            list_title=list_title,
            instruments=instruments,
        )
        self.queue = RequestQueue(
            path=queue_path,
            hackmd_token=hackmd_token,
            hackmd_tags=hackmd_tags,
            hackmd_queue_title=queue_title,
        )

    async def send_message(self, ctx: commands.Context, message: str):
        if self.message_prefix:
            await ctx.send(f"{self.message_prefix}: {message}")
        else:
            await ctx.send(message)

    async def event_ready(self):
        print(f"Logged in as: {self.nick}")
        print(f"User id: {self.user_id}")
        print(f"Queue: {self.queue.note.url}")
        print(f"Songlist: {self.songs.note.url}")
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
        song = self.songs.get(int(cmd_arg))
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
            f"1: Song unter {self.songs.url} finden. "
            "2: Request-Befehl kopieren. "
            "3: Request-Befehl im Chat einfügen.",
        )

    @commands.command()
    async def rules(self, ctx: commands.Context):
        await self.send_message(
            ctx,
            "1: Request kostet nichts. "
            "2: 5 Euro Spende dein Song kommt als nächstes.",
        )

    @commands.command()
    async def allrequests(self, ctx: commands.Context):
        await self.send_message(
            ctx, f"die gesamte Warteschlange gibts unter {self.queue.note.url}"
        )


if __name__ == "__main__":
    with open("./config.toml", mode="rb") as tc:
        config = tomllib.load(tc)

    bot = Bot(
        csv_path=config["Local"]["SONGLIST"],
        hackmd_token=config["HACKMD"]["HACKMDTOKEN"],
        hackmd_tags=config["HACKMD"]["HACKMDTAG"],
        queue_path=config["Local"]["QUEUE_FILE"],
        twitch_token=config["Twitch"]["ACCESS_TOKEN"],
        bot_prefix=config["Twitch"]["BOT_PREFIX"],
        channel=config["Twitch"]["CHANNEL"],
        cfsm=config["Local"]["LIST_CFSM"],
        instruments=config["Local"]["INSTRUMENTS"],
        delimiter=config["Local"]["LIST_DELIMITER"],
        list_title=config["HACKMD"]["LISTTITLE"],
        queue_title=config["HACKMD"]["QUEUETITLE"],
        message_prefix=config["Twitch"]["MESSAGE_PREFIX"],
    )
    bot.run()
