# requestnonsense
let's request some songs in twitch channels you do not need to own

## get started

1. clone
2. ```python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp example.env .env```
3. get twitch chat bot token via https://twitchtokengenerator.com/
4. get hackmd.io api token
5. put api tokens in .env
6. get songlist csv - (customs forge song manager will create one for you)
7. python requestnonsense.py```

## songlist csv format

Customs Forge Song Manager CSV-Format starts with a line denoting the delimiter.
We alaways assume ";" und skip over it. If you don't use CFSM, include a blank line in your csv first

We rely on Columns "Artist", "Title" and "Arrangements" in songlist, additional columns are ignored.


