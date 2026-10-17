---
name: plaza
description: Look up what DragonRealms player shops charge for an item, from drservice.info's Plaza Shop Browser, through `uv run python tools/plaza.py --grep WORD`. Use before guessing any price — a ;kiosk resale, a purchase, "what does X sell for", "is this a good price", what other Traders' shops ask — and whenever a script or answer needs a market price.
---

# Shop prices from the Plaza

The Plaza Shop Browser scans every player shop in Crossing, Riverhaven
and Shard. `tools/plaza.py` downloads its export at most once a day
into `~/.revenant/plaza` and prints one line per item, cheapest first:
item | shop | city | price | last scanned.

```sh
uv run python tools/plaza.py --grep "gem pouch"         # an item by a word of its name
uv run python tools/plaza.py --grep pouch --city shard  # one city (a part of its name)
uv run python tools/plaza.py --grep ring --under 50     # under 50 Kronar platinum
```

1. **Ask it before guessing a price.** Say which shop and city a figure
   came from, and the scan date: an item scanned weeks ago may be sold.
2. **Read the coin.** A Riverhaven or Shard price is in Lirums or
   Dokoras, with its Kronar value beside it; `--under` compares Kronars.
3. **A listed price is an asking price**, not a sale: the export says
   what shops ask, never what sold.
4. **Never `--refresh` in a loop**, and never script repeated downloads:
   the site is one person's, and its owner has not been asked about
   more than a daily download (#577).
5. **No names in the repo.** The export names each shop's owner; the
   tool never prints them, and nothing from it goes into a fixture.
