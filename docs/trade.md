# Trading

`;trade` runs a Trader's caravan contracts in Zoluren and Ilithi, and to Riverhaven: it takes a contract, has the caravan lead to its town, collects the pay, and goes again. Every contract is logged to history.db.

```
;trade            run contracts until stopped
;trade interprovince  the same, each contract for another province where one is offered
;trade return     typed while it runs: deliver what is held, take no new contract, return the caravan
;trade history    per route: contracts, pay and profit in Kronars (Dokoras at 1.386, Lirums at 1.25), minutes
```

- Start at an outpost with your caravan at it: in Zoluren the Crossing, Arthe Dale, Stone Clan, Dirge, Wolf Clan, Tiger Clan or Leth Deriel (Kronars); in Ilithi Shard, Fayrin's Rest, Steelclaw Clan or Darkling Wood (Dokoras); Riverhaven (Lirums).
- Leth Deriel is across the Segoltha: the caravan is led to the Crossing and follows you onto Alfren's Ferry (77 Kronars for the goods; with none on you, `;bank` fetches them while the caravan waits at the dock), then leads on from the south bank.
- With no caravan, `;trade` rents one at the outpost's clerk: RENT CARAVAN, 400 Kronars or 288 Dokoras paid up front, drawn at a teller when the purse is short.
- Wear or carry a feedbag with grass in it; the caravan is fed before every lead. While the caravan leads, `;trade` forages grass into the feedbag until it holds 60.
- A led character follows the caravan through any roundtime, so a lead trains in place: the profile's `lead_training` (File → Character Profile…) names the scripts, today `perform` (`;perform once here`, your `instrument`). It is ended when the caravan arrives; the grass forage waits while it plays.
- Each leg: deliver and get paid, PAY CLERK, ASK MINISTER FOR CONTRACT, the clerk loads the crate, feed, LEAD TO the contract's town.
- The minister charges the goods' wholesale price and dues to the issuing town; they are paid at that town's clerk before its next contract. When the purse is short, `;trade` draws the dues at the nearest teller.
- After a delivery in the Crossing, Dirge, Leth Deriel, Shard or Riverhaven, the towns with a teller near the clerk, `;trade` banks the pay through `;bank`, keeping 20,000 copper of the province's coin for the dues and fees ahead.
- `;trade return`, typed while it runs, ends by returning the rented caravan at the clerk, RETURN CARAVAN, once its storage box is empty; with anything in the box the caravan is kept. `;stop trade` keeps it too. The next `;trade` rents another.
- `;trade interprovince` asks the broker instead of the minister (ASK BROKER FOR CONTRACT) in the Crossing (the Foreign Trade Office, north of the clerk), Shard (Brickwell Tower's Provincial Broker) and Riverhaven (the Foreign Trade Office, east of the guild lobby); elsewhere the minister. The broker's charge is paid at the clerk before the crate is loaded.
- A contract between Zoluren and Ilithi goes by Leth Deriel and the Obsidian Pass gondola: the caravan follows you from Leth's outpost to Shard's and rides the gondola with you.
- A contract for Riverhaven (the Crossing's broker offers them) is led to Dirge, where `;bank` tops the purse up to 500 Lirums for the Faldesu ferry's fare (152 for a caravan of eel); then LEAD TO RIVERHAVEN ends at the ferry, and the caravan follows you aboard and up to Town Hall Road. Back, it rides the ferry and leads to Dirge from the riverbank south of the dock. After the delivery at Riverhaven `;trade` stops, the caravan kept: it takes no contract there yet.
- A contract for any other town (the rest of Therengia, Forfedhdar) is left with you, unpaid and unloaded.
- `;trade` does not fight. On the road you follow the caravan; watch the window.

The `contracts` table in history.db holds one row per contract: issued, origin, destination, goods, wholesale, dues, worth, fee, delivered, paid, and province (Zoluren, Ilithi, Therengia, or Interprovince for a contract to another province).
