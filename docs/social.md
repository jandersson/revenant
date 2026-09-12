# Between characters: coins, flags and the ask

Two of your own characters can meet in a room and pass coins, and a
stranger can heal you for the asking — once the recipient's own flags
allow it. This file records what was captured doing both on
2026-09-11/12 with a circle-1 Paladin and an older character on the
other account, so the defaults are not relearned. Healing itself is
[healing.md](healing.md).

## Coins are handed, not sent

There is no transfer between characters through the bank: BANK
TRANSFER moves one character's money between their own accounts.
Coins change hands in person — walk both to the same room (`;go2
<room>` from one session to the room the other stands in; the map
knows the bank teller and the gates) and

```
GIVE <person> <#> <metal>              the province's currency
GIVE <person> <#> <metal> <currency>   e.g. GIVE Lanival 2 plat Kronars
```

No ACCEPT is needed for coins (items need one). Two things refuse
it, per Elanthipedia's [GIVE command](https://elanthipedia.play.net/Give_command):
the recipient's AVOID COINS flag, and a giver whose provincial debt
is too great. The refusal is shown to the giver only — captured:

```
> give lanival 2 plat
Lanival is not interested in taking coins from you.
```

and the recipient sees nothing at all.

## A new character refuses coins by default

`AVOID` lists the flags; `!` means no. A circle-1 character's list
read `!COINS` and `!CRIME` with everything else allowed (captured),
so he refused every coin gift without knowing it. `AVOID COINS`
clears it ("You're now allowing attempts to hand you coins."),
`AVOID !COINS` restores the guard. The other flags — JOINING,
DRAGGING, HOLDING, TEACHING, WHISPERING, DANCING, TOUCHING — are the
same shape, and `AVOID !ALL` / `AVOID ALL` set or clear them all;
FLAG, SET and TOGGLE hold the rest of a character's switches.

Once the flag was cleared the same GIVE went through and the coins
landed.

## Debt

The province lends when you cannot pay: a stat trainer's fee with
no coins in hand (2 Kronars per TDP, [training.md](training.md)), a
fine, a fee. INFO lists it under Debt with a copper total —
captured 2026-09-12: "You owe 1 gold, 5 silver and 1 bronze Kronars
to the Principality of Zoluren. (1510 copper Kronars)" — and it is
the giver's debt that GIVE refuses on. It is paid in person at a
debt collector's office (the map tags them `debt`; Zoluren's are in
Crossing's Town Hall and Leth Deriel) with `PAY ALL` or `PAY
<amount>`, or remotely through the urchin runners' `BANK DEBT`, a
SimuCoins service. `;debt` shows what you carry and owe; `;debt pay`
walks to the nearest teller for the shortfall (`WITHDRAW <#>
<denomination>`, one coin type per command), then to the office,
pays, and trusts only INFO's answer. The PAY and WITHDRAW wordings
are not captured yet; the first run is where they get pinned.

## The ask

Empaths heal for a sentence said aloud in their guild's courtyard,
and a coin-less character with a wounded friend on the other account
is helped the same way: say what you need where people are. The
captured exchange is in [healing.md](healing.md).
