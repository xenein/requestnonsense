#!/usr/bin/env python3

from decouple import config
from twitchio.ext import commands
import csv
import pickle
import random
import requests
import time
import os


def create_note(content: str) -> str:
    headers = {"Authorization": f"Bearer {config('HACKMDTOKEN')}"}
    payload = {
        "readPermission": "guest",
        "writePermission": "owner",
        "commentPermission": "disabled",
        "content": content,
    }

    _response = requests.post(
        "https://api.hackmd.io/v1/notes", headers=headers, json=payload
    )
    return f"https://hackmd.io/{_response.json().get('id')}"


def update_note(content: str, note_url: str) -> bool:
    note_id = note_url.split("/")[-1]
    headers = {"Authorization": f"Bearer {config('HACKMDTOKEN')}"}
    payload = {
        "readPermission": "guest",
        "writePermission": "owner",
        "commentPermission": "disabled",
        "content": content,
    }

    _response = requests.patch(
        f"https://api.hackmd.io/v1/notes/{note_id}", headers=headers, json=payload
    )

    return _response.status_code == 202


def generate_requests_markdown(queue: list) -> str:
    requests_markdown = ["# Xenias mystische Warteschlange", "", "| Pos | Song | User |", "| --- | --- | --- |"]
    for idx, request in enumerate(queue, start=1):
        requests_markdown.append(f"| {idx} | {request[-2]} | {request[-1]} |")

    return "\n".join(requests_markdown)


queue = []
requests_url = create_note(
    "# Xenias mystische Warteschlange \n Gerade beeindruckend leer."
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

    # TODO: select arrangements via decouple
    song_set = set()
    for line in reader:
        if "Bass" in str(line.get("Arrangements")):
            song_set.add((line.get("Artist"), line.get("Title")))

    song_list = list(song_set)
    song_list.sort()
    for idx, song in enumerate(song_list, start=1):
        songs[idx] = f"{song[0]} - {song[1]}"

    songlist_markdown = [
        """# Xenias mystische Songliste

Such dir einen Song raus, kopier das Request-Command und fügs im Chat ein.



| Artist | Title | Command |
| --- | --- | --- |"""
    ]
    for idx, song in enumerate(song_list, start=1):
        songlist_markdown.append(f"| {song[0]} | {song[1]} | ?request {idx} |")

    songs_url = create_note("\n".join(songlist_markdown))


def get_index_for_user(user: str) -> int | None:
    for idx, entry in enumerate(queue):
        if entry[-1] == user:
            return idx
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

    @commands.command()
    async def meow(self, ctx: commands.Context):
        print("meow awaited")
        print(ctx.message.content)
        await ctx.send("meow!")

    @commands.command()
    async def request(self, ctx: commands.Context):
        """
        request command: add song as non prio, non current request to the end of queue OR
        change song data in the request for a given user
        """
        print("request awaited")
        cmd_arg = ctx.message.content.split(" ", maxsplit=1)[1]
        song = songs.get(int(cmd_arg))
        message: str
        if song:
            current = False
            prio = False
            moment = time.time()
            requestee = ctx.author.name

            if idx := get_index_for_user(requestee) is not None:
                request_tuple = (current, prio, queue[idx][2], song, requestee)
                queue[idx] = request_tuple
                message = (
                    f"@{ctx.author.name}: Dein Request wurde aktualisert zu {song}"
                )
            else:
                request_tuple = (current, prio, moment, song, requestee)
                queue.append(request_tuple)
                message = (
                    f"@{ctx.author.name}: Dein Request für {song} ist eingetragen."
                )

            safe_queue()
        else:
            print(f"song {song} not found")
            message = f"@{ctx.author.name} konnte keinen Song für {ctx.message} finden"
        await ctx.send(message)

    @commands.command()
    async def upgrade_request(self, ctx: commands.Context):
        if ctx.author.is_mod:
            cmd_arg = ctx.message.content.split(" ", maxsplit=1)[1:]
            
            if idx := get_index_for_user(cmd_arg) is not None:
                request = queue[idx]
                queue[idx] = (request[0], True, request[2], request[3], request[4])
                queue.sort()
                safe_queue()
                print(f"Der Request von {request[-1]} hat jetzt prio")
                await ctx.send(
                    f"@{ctx.author.name}: Der Request von {request[-1]} hat jetzt prio"
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
        if (idx := get_index_for_user(ctx.message.author.name)) is not None:
            message = f"Dein Request ist aktuell auf Platz {idx} in der Warteschlange"
        else:
            message = "Du hast anscheinend gar keinen Song in der Warteschlange"
        await ctx.send(f"@{ctx.message.author.name}: {message}")

    @commands.command()
    async def next(self, ctx: commands.Context):
        if ctx.author.is_mod:
            top_song = queue[0]
            if top_song[0]:
                queue.remove(top_song)
            new_top = queue[0]
            queue[0] = (True,) + new_top[1:]
            safe_queue()
            message = f"Nächster Song: {new_top[-2]} requestet von {new_top[-1]}"
            print(message)
            await ctx.send(message)
        else:
            await ctx.send(f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl")

    @commands.command()
    async def randomize(self, ctx: commands.Context):
        if ctx.author.is_mod:
            top_song = queue[0]
            if top_song[0]:
                queue.remove(top_song)
            new_top = random.choice(queue)
            queue[0] = (True,) + new_top[1:]
            message = f"Nächster Song: {new_top[-2]} requestet von {new_top[-1]}"
            queue.remove(new_top)
            safe_queue()
            print(message)
            await ctx.send(message)
        else:
            await ctx.send(f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl")

    @commands.command()
    async def scam(self, ctx: commands.Context):
        cmd_arg = ctx.message.content.split(" ", maxsplit=1)[1:]
        idx = int(cmd_arg)
        if ctx.author.is_mod:
            top_song = queue[0]
            if top_song[0]:
                queue.remove(top_song)
            new_top = queue[idx]
            queue[0] = (True,) + new_top[1:]
            message = f"Nächster Song: {new_top[-2]} requestet von {new_top[-1]}"
            queue.remove(new_top)
            safe_queue()
            print(message)
            await ctx.send(message)
        else:
            await ctx.send(f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl")

    @commands.command()
    async def help(self, ctx: commands.Context):
        await ctx.send(
            f"1: Song unter {songs_url} finden. 2: Request-Befehl kopieren. 3. Request-Befehl im Chat einfügen."
        )

    @commands.command()
    async def rules(self, ctx: commands.Context):
        await ctx.send(
            "1: Request kostet nichts. 2: 1 verschenkter Sub: wir schieben deinen Request hoch. 3. Iron Maiden und Dragonforce nur für eine Dono von Mindestens 25 €."
        )

    @commands.command()
    async def allrequests(self, ctx: commands.Context):
        await ctx.send(f"die gesamte Warteschlange gibts unter {requests_url}")


if __name__ == "__main__":
    bot = Bot()
    bot.run()
