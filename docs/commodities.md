# Commodities

`;commodities` reads a Trader's commodity pits and carries a good from the pit where it is cheap to one where it is dear. Every board it reads is logged to history.db, so prices and stock can be watched over days before money goes in. What the trades earned, beside caravan contracts: [caravans.md](caravans.md#commodities-for-comparison).

```
;commodities          walk to each pit, the nearest first, and read its board
;commodities read     read the board of the pit you stand in
;commodities plan     the best trade from each pit by the boards read in the last 6 hours; nothing sent
;commodities trade    buy the best at the nearest pit, walk the guild's pack animal to the buyer's town, sell it there
```

| Pit | Room | Shipment clerk | The animal waits at |
|---|---|---|---|
| The Crossing | Traders' Guild, The Pit (19275) | Shipment Center (8916) | Commerce Avenue |
| Arthe Dale | Swotting Hall, Trader's Pit (9000) | Trader's Center (8999) | Cul-de-sac |
| Leth Deriel | Eshar's Trading Post, The Pit (13550) | Main Room (9004) | Oakenheart Circle |

- Buying is ORDER <n> <good> at the pit clerk: the board price a unit plus the guild's cut (about 3%), from the purse. The guild lends a pack animal and loads the goods on it outside.
- Selling is SELL <n> <good> at the buyer's shipment clerk, the animal outside: the board price, no cut. The pit clerk does not buy.
- A board's stock words (`Surplus!`, `Good Stores`, `Going Fast`, `Nearly Out!`, `*SOLD OUT!*`) are unit bands per good. A pit with a surplus buys none, so `trade` buys only as many as the seller surely holds and the buyer takes short of Surplus, and only for 2,000 Kronars clear or more.
- The pack animal follows you room by room (TELL <animal> TO FOLLOW) and rides Alfren's Ferry; it will not come indoors.
- Before selling, the buyer's board is read again; a good now in Surplus or below what was paid stays on the animal, said.
- A trade stopped on the way is carried on by the next `;commodities trade`, started beside the animal.

The `commodities` table holds one row per good per board read (pit, good, price, stock word, time); `commodity_trades` one row per trade (good, units, where bought, price, cut, where sold, pay, times), in copper Kronars.
