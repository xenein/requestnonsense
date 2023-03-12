# requestnonsense
let's request some songs in twitch channels you do not need to own

## get started

1. clone
2. `python -m venv venv`
3. `source venv/bin/activate`
4. `pip install -r requirements.txt`
5. `cp example.env .env`
6. get twitch chat bot token via https://twitchtokengenerator.com/
7. get hackmd.io api token
8. put api tokens in .env
9. build songlist csv - (customs forge song manager will create one for you)
10. `python requestnonsense.py`

## songlist csv format

Customs Forge Song Manager CSV-Format starts with a line denoting the delimiter.
We always assume ";" and skip over the first line. If you don't use CFSM, include a blank line in your csv first. (This might chance, keep an eye on here)

We rely on Columns "Artist", "Title" and "Arrangements" in songlist, additional columns are ignored.
If your csv does not have arrangements, you can go with `INSTRUMENTS=` in .env - this will simply use all songs.

## why hackmd?

- Request-Queue and Songlist with request commands should available in the web. Request-Queue will change throughout your stream, those changes should be automatically synced to browsers. HackMD will do that for us. 
- HackMD uses markdown. It is easy convenient to build markdown sources for songlist and requests. 
- HackMD has a free tier including more than 1000 API-Requests per month. That should last for a while

## so what can you do?

everything happens in twitchchat. Commands may start with ! or ?. 

### Everyone can:

- `?request <songID>` - add your song to the queue or replace your request while keeping your position in the queue. see `?rules` for link to songlist with available songs
- `?allrequest` - retrieve a link with the full queue
- `?position` - bot will answer with your current position in the queue
- `?help` - bot will answer with a short explanation and the link with the songlist
- `?rules` - bot will give a short rules text
- `?meow`- bot will meow back to you

### Mods can: 

- `?next`- if no song is active, set the song at the top of the queue active. otherwise remove the top song from queue and set next one active
- `?randomize` - same as next, but use a random song to put on top
- `?scam <position>` - same as next, but use song at <position> in queue to put on top 
- `?upgrade_request <user>` - promote request from <user> in priority position. Those are at the top of queue, also sorted by insert time

