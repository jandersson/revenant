# Trading

`;trade` runs a Trader's caravan contracts around Zoluren: it takes a contract, has the caravan lead to its town, collects the pay, and goes again. Every contract is logged to history.db.

```
;trade            run contracts until stopped
;trade return     deliver what is held, take no new contract
;trade history    per route: contracts, pay, profit, minutes
```

- Start at an outpost in the Crossing, Arthe Dale, Stone Clan, Dirge, Wolf Clan or Tiger Clan, with your caravan at the outpost.
- Rent a caravan with RENT CARAVAN at a shipment clerk (400 Kronars, paid up front).
- Wear or carry a feedbag with grass in it; the caravan is fed before every lead.
- Each leg: deliver and get paid, PAY CLERK, ASK MINISTER FOR CONTRACT, the clerk loads the crate, feed, LEAD TO the contract's town.
- The minister charges the goods' wholesale price and dues to the issuing town; they are paid at that town's clerk before its next contract. When the purse is short, `;trade` draws the dues at the nearest teller.
- A contract for Leth Deriel or another province is left with you: `;trade` leads only where no ferry or gondola is needed.
- `;trade` does not fight. On the road you follow the caravan; watch the window.

The `contracts` table in history.db holds one row per contract: issued, origin, destination, goods, wholesale, dues, worth, fee, delivered and paid.
