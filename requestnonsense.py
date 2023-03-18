#!/usr/bin/env python3
"""
so, requests are NamedTuples.
like so (waiting: bool, non_prio: bool, timestamp: float, song: str, requestee: str)
waiting is opposite of current, non_prio <-> prio
we put them in a list. why?
we can use .sort() and get it nicely ordered

what else?
everyone in chat can request
you can have one request in queue
if you send another, you keep your place in the queue, song is changed though

the list of available songs as well as the current queue are pushed to hackmd-notes
"""

from decouple import config, Csv
from twitchio.ext import commands
from typing import NamedTuple

import csv
import pickle
import random
import requests
import time
import os

# config
hackmdtags = f"---\ntags: {config('HACKMDTAG', default='requestnonsense')}\n---"
hackmdheaders = {"Authorization": f"Bearer {config('HACKMDTOKEN')}"}

instruments = config("INSTRUMENTS", cast=Csv(), default=[])


# request-tuples
class RequestTuple(NamedTuple):
    """Requests are handled in tuples. Fields within requests can be accessed by name, too"""

    waiting: bool
    non_prio: bool
    timestamp: float
    song: str
    requestee: str


def create_note(content: str) -> str:
    payload = {
        "readPermission": "guest",
        "writePermission": "owner",
        "commentPermission": "disabled",
        "content": content,
    }

    _response = requests.post(
        "https://api.hackmd.io/v1/notes", headers=hackmdheaders, json=payload
    )
    return f"https://hackmd.io/{_response.json().get('id')}"


def update_note(content: str, note_url: str) -> bool:
    note_id = note_url.split("/")[-1]
    payload = {
        "readPermission": "guest",
        "writePermission": "owner",
        "commentPermission": "disabled",
        "content": content,
    }

    _response = requests.patch(
        f"https://api.hackmd.io/v1/notes/{note_id}", headers=hackmdheaders, json=payload
    )

    return _response.status_code == 202


def generate_requests_markdown(queue: list[RequestTuple]) -> str:
    if len(queue) == 0:
        return f"{hackmdtags}# {config('QUEUETITLE', default='Queue')}\n Beeindruckend leer hier"
    requests_markdown = [
        f"{hackmdtags}# {config('QUEUETITLE', default='Queue')}",
        "",
        "| Pos | Song | User |",
        "| --- | --- | --- |",
    ]
    for idx, request in enumerate(queue, start=1):
        requests_markdown.append(f"| {idx} | {request.song} | {request.requestee} |")

    return "\n".join(requests_markdown)


queue: list[RequestTuple] = []
requests_url = create_note(
    f"{hackmdtags}# {config('QUEUETITLE', default='Queue')}\n Gerade beeindruckend leer."
)
if os.path.exists(config("QUEUE_FILE")):
    with open(config("QUEUE_FILE"), mode="rb") as fh:
        queue = pickle.load(fh)
    update_note(generate_requests_markdown(queue), requests_url)

songs = dict()
songs_url = ""
if os.path.exists(config("SONGLIST")):
    with open(config("SONGLIST")) as fh:
        csv_lines = fh.readlines()[1:]
    reader = csv.DictReader(csv_lines, delimiter=";")

    song_set = set()
    for line in reader:
        if instruments:
            for instrument in str(instruments):
                if instrument in str(line.get("Arrangements")):
                    song_set.add((line.get("Artist"), line.get("Title")))
        else:
            song_set.add((line.get("Artist"), line.get("Title")))

    song_list = list(song_set)
    song_list.sort()
    for idx, song in enumerate(song_list, start=1):
        songs[idx] = f"{song[0]} - {song[1]}"

    songlist_markdown = [
        hackmdtags,
        f"""# {config("LISTTITLE", default="List")}

Such dir einen Song raus, kopier das Request-Command und fügs im Chat ein.



| Artist | Title | Command&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; |
| --- | --- | --- |""",
    ]
    for idx, song in enumerate(song_list, start=1):
        songlist_markdown.append(f"| {song[0]} | {song[1]} | ?request {idx} |")

    songs_url = create_note("\n".join(songlist_markdown))


def get_index_for_user(user: str) -> int | None:
    for idx, entry in enumerate(queue, start=1):
        if entry[-1] == user:
            return idx
    return None


def get_request_for_user(user: str) -> RequestTuple | None:
    for entry in queue:
        if entry[-1] == user:
            return entry
    return None


def safe_queue():
    with open(config("QUEUE_FILE"), mode="wb") as fh:
        pickle.dump(queue, fh)
    update_note(generate_requests_markdown(queue), requests_url)


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=str(config("ACCESS_TOKEN")),
            prefix=["?", "!"],
            initial_channels=[config("CHANNEL")],
        )

    async def event_ready(self):
        print(f"Logged in as: {self.nick}")
        print(f"User id: {self.user_id}")
        await self.connected_channels[0].send("Requestnonse bereit")

    @commands.command()
    async def meow(self, ctx: commands.Context):
        print("meow awaited")
        await ctx.send("meow!")

    @commands.command()
    async def request(self, ctx: commands.Context):
        """
        request command: add song as non prio, non current request to the end of queue OR
        change song data in the request for a given user
        """
        print("request awaited")
        message = str(ctx.message.content)
        cmd_arg = message.split(" ", maxsplit=1)[1]
        song = songs.get(int(cmd_arg))
        message: str
        if song:
            waiting = True
            non_prio = True
            moment = time.time()
            requestee = str(ctx.author.name)

            if (request := get_request_for_user(requestee)) is not None:
                request_tuple = RequestTuple(
                    request.waiting,
                    request.non_prio,
                    request.timestamp,
                    song,
                    requestee,
                )
                queue.append(request_tuple)
                queue.remove(request)
                queue.sort()
                message = (
                    f"@{ctx.author.name}: Dein Request wurde aktualisert zu {song}"
                )
            else:
                request_tuple = RequestTuple(waiting, non_prio, moment, song, requestee)
                queue.append(request_tuple)
                message = (
                    f"@{ctx.author.name}: Dein Request für {song} ist eingetragen."
                )

            safe_queue()
        else:
            print(f"song {song} not found")
            message = f"@{ctx.author.name} konnte keinen Song für {ctx.message} finden"
        print(message)
        await ctx.send(message)

    @commands.command()
    async def upgrade_request(self, ctx: commands.Context):
        if ctx.author.is_mod:
            print("upgrade awaited")
            command = str(ctx.message.content)
            cmd_arg = command.split(" ", maxsplit=1)[1]
            if cmd_arg.startswith("@"):
                cmd_arg = cmd_arg[1:]

            if (request := get_request_for_user(cmd_arg)) is not None:
                queue.append(
                    RequestTuple(
                        request.waiting,
                        False,
                        request.timestamp,
                        request.song,
                        request.requestee,
                    )
                )
                queue.remove(request)
                queue.sort()
                safe_queue()
                print(f"Der Request von {request.requestee} hat jetzt prio")
                await ctx.send(
                    f"@{ctx.author.name}: Der Request von {request.requestee} hat jetzt prio"
                )
            else:
                print(f"{cmd_arg} hat keine Request in der Warteschlange")
                await ctx.send(
                    f"@{ctx.author.name}: {cmd_arg} hat keine Request in der Warteschlange"
                )
        else:
            await ctx.send(f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl")

    @commands.command()
    async def position(self, ctx: commands.Context):
        if (idx := get_index_for_user(str(ctx.message.author.name))) is not None:
            message = f"Dein Request {queue[idx-1].song} ist aktuell auf Platz {idx} in der Warteschlange"
        else:
            message = "Du hast anscheinend gar keinen Song in der Warteschlange"
        await ctx.send(f"@{ctx.message.author.name}: {message}")

    @commands.command()
    async def next(self, ctx: commands.Context):
        if ctx.author.is_mod:
            if len(queue) > 0:
                top_song = queue[0]
                if not top_song.waiting:
                    # not waiting -> song was active
                    queue.remove(top_song)
                if len(queue) > 0:
                    new_top = queue[0]
                    queue[0] = RequestTuple(
                        False,
                        new_top.non_prio,
                        new_top.timestamp,
                        new_top.song,
                        new_top.requestee,
                    )
                    safe_queue()
                    message = f"Nächster Song: {new_top.song} requestet von {new_top.requestee}"
                else:
                    message = "Queue leer, säd"
            else:
                message = "Queue leer, säd"
            print(message)
            await ctx.send(message)
        else:
            await ctx.send(f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl")

    @commands.command()
    async def randomize(self, ctx: commands.Context):
        if ctx.author.is_mod:
            if len(queue) == 0:
                return
            top_song = queue[0]
            if not top_song[0]:
                # [0] is waiting -> not waiting -> song was active
                queue.remove(top_song)
            new_top = random.choice(queue)
            queue.insert(
                0,
                RequestTuple(
                    False,
                    new_top.non_prio,
                    new_top.timestamp,
                    new_top.song,
                    new_top.requestee,
                ),
            )
            message = f"Nächster Song: {new_top.song} requestet von {new_top.requestee}"
            queue.remove(new_top)
            safe_queue()
            print(message)
            await ctx.send(message)
        else:
            await ctx.send(f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl")

    @commands.command()
    async def scam(self, ctx: commands.Context):
        print("Scam awaited")
        message = str(ctx.message.content)
        cmd_arg = message.split(" ", maxsplit=1)[1]

        try:
            idx = int(cmd_arg)
        except ValueError:
            print(f"{cmd_arg} nach int casten nicht so die Idee.")
            await ctx.send(f"{cmd_arg} ist anscheinend keine Zahl")
            return

        if idx >= len(queue):
            await ctx.send(f"@{ctx.author.name}: So lang ist Queue nicht. Upsi")
            return
        if ctx.author.is_mod:
            if len(queue) > 0:
                top_song = queue[0]
                if not top_song[0]:
                    # [0] is waiting -> not waiting -> song was active
                    queue.remove(top_song)
                new_top = queue[idx - 1]
                queue.remove(new_top)
                queue.insert(
                    0,
                    RequestTuple(
                        False,
                        new_top.non_prio,
                        new_top.timestamp,
                        new_top.song,
                        new_top.requestee,
                    )
                )
                message = f"Nächster Song: {new_top.song} requestet von {new_top.requestee}"
                safe_queue()
            else:
                message = "Queue leer, säd"
            print(message)
            await ctx.send(message)
        else:
            await ctx.send(f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl")

    @commands.command()
    async def help(self, ctx: commands.Context):
        await ctx.send(
            f"1: Song unter {songs_url} finden. "
            "2: Request-Befehl kopieren. "
            "3: Request-Befehl im Chat einfügen."
        )

    @commands.command()
    async def rules(self, ctx: commands.Context):
        await ctx.send(
            "1: Request kostet nichts. "
            "2: 2 verschenkter Subs: wir schieben deinen Request hoch. "
            "3. Iron Maiden und Dragonforce nur für eine Dono von Mindestens 25 €."
        )

    @commands.command()
    async def allrequests(self, ctx: commands.Context):
        await ctx.send(f"die gesamte Warteschlange gibts unter {requests_url}")


if __name__ == "__main__":
    bot = Bot()
    bot.run()
