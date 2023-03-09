#!/usr/bin/env python3

from decouple import config
from twitchio.ext import commands
import pickle
import random
import time
import os

queue = []
requests_url = ""
if os.path.exists(config("QUEUE_FILE")):
    with open(config("QUEUE_FILE")) as fh:
        queue = pickle.load(fh)


songs = dict()
songs_url = ""
if os.path.exists(config("SONGLIST")):
    with open(config("SONGLIST")) as fh:
        # dictreader nonsense
        for line in fh:
            print(line)


def get_index_for_user(user: str) -> int:
    for idx, entry in enumerate(queue):
        if entry[-1] == user:
            return idx
    return None


def safe_queue():
    with open(config("QUEUE_FILE", "wb")) as fh:
        pickle.dump(queue, fh)


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=config("ACCESS_TOKEN"),
            prefix=["?", "!"],
            initial_channels=[config("CHANNEL")],
        )

    async def event_ready(self):
        print(f"Logged in as: {self.nick}")
        print(f"User id: {self.user_id}")

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
        song = songs.get(ctx.message)
        message: str
        if song:
            current = False
            prio = False
            moment = time.time()
            requestee = ctx.author.name

            if idx := get_index_for_user(ctx.author.name) is not None:
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
            if idx := get_index_for_user(ctx.message) is not None:
                request = queue[idx]
                queue[idx] = (request[0], True, request[2], request[3], request[4])
                queue.sort()
                safe_queue()
                print(f"Der Request von {request[-1]} hat jetzt prio")
                await ctx.send(
                    f"@{ctx.author.name}: Der Request von {request[-1]} hat jetzt prio"
                )
            else:
                print(f"{ctx.message} hat keine Request in der Warteschlange")
                await ctx.send(
                    f"@{ctx.author.name}: {ctx.message} hat keine Request in der Warteschlange"
                )
        else:
            await ctx.send(f"@{ctx.author.name}: Das ist ein Mod-Only-Befehl")

    @commands.command()
    async def position(self, ctx: commands.Context):
        if idx := get_index_for_user(ctx.message.author.name) is not None:
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
        if ctx.author.is_mod:
            top_song = queue[0]
            if top_song[0]:
                queue.remove(top_song)
            new_top = queue[ctx.message]
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
