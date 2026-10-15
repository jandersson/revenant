# Trading

`;trade` runs a Trader's caravan contracts in Zoluren or Ilithi: it takes a contract, has the caravan lead to its town, collects the pay, and goes again. Every contract is logged to history.db.

```
;trade            run contracts until stopped
;trade broker     the same, each contract from the broker where one is known
;trade return     typed while it runs: deliver what is held, take no new contract, return the caravan
;trade history    per route: contracts, pay, profit, minutes
```

- Start at an outpost with your caravan at it: in Zoluren the Crossing, Arthe Dale, Stone Clan, Dirge, Wolf Clan, Tiger Clan or Leth Deriel (Kronars); in Ilithi Shard, Fayrin's Rest, Steelclaw Clan or Darkling Wood (Dokoras).
- Leth Deriel is across the Segoltha: the caravan is led to the Crossing and follows you onto Alfren's Ferry (77 Kronars for the goods), then leads on from the south bank.
- With no caravan, `;trade` rents one at the outpost's clerk: RENT CARAVAN, 400 of the province's coin paid up front, drawn at a teller when the purse is short.
- Wear or carry a feedbag with grass in it; the caravan is fed before every lead. While the caravan leads, `;trade` forages grass into the feedbag until it holds 60.
- A led character follows the caravan through any roundtime, so a lead trains in place: the profile's `lead_training` (File → Character Profile…) names the scripts, today `perform` (`;perform once here`, your `instrument`). It is ended when the caravan arrives; the grass forage waits while it plays.
- Each leg: deliver and get paid, PAY CLERK, ASK MINISTER FOR CONTRACT, the clerk loads the crate, feed, LEAD TO the contract's town.
- The minister charges the goods' wholesale price and dues to the issuing town; they are paid at that town's clerk before its next contract. When the purse is short, `;trade` draws the dues at the nearest teller.
- After a delivery in the Crossing, Dirge, Leth Deriel or Shard, the towns with a teller near the clerk, `;trade` banks the pay through `;bank`, keeping 20,000 copper of the province's coin for the dues and fees ahead.
- `;trade return`, typed while it runs, ends by returning the rented caravan at the clerk, RETURN CARAVAN, once its storage box is empty; with anything in the box the caravan is kept. `;stop trade` keeps it too. The next `;trade` rents another.
- `;trade broker` asks the broker instead of the minister (ASK BROKER FOR CONTRACT) in the Crossing (the Foreign Trade Office, north of the clerk) and Shard (Brickwell Tower's Provincial Broker, untried); elsewhere the minister. The broker's charge is paid at the clerk before the crate is loaded.
- A contract between Zoluren and Ilithi goes by Leth Deriel and the Obsidian Pass gondola: the caravan follows you from Leth's outpost to Shard's and rides the gondola with you. A contract for any other province is left with you.
- `;trade` does not fight. On the road you follow the caravan; watch the window.

The `contracts` table in history.db holds one row per contract: issued, origin, destination, goods, wholesale, dues, worth, fee, delivered and paid.
