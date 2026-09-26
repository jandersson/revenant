# Between characters

Coins move between characters only by hand, in the same room — and a new character refuses them until a flag is cleared.

## Handing coins

There is no bank transfer between characters (BANK TRANSFER moves money between one character's own accounts). Walk both to one room (`;go2`) and:

```
GIVE <person> <#> <metal>              the province's currency
GIVE <person> <#> <metal> <currency>   e.g. GIVE Lanival 2 plat Kronars
```

No ACCEPT is needed for coins. Two things refuse it, and only the giver sees the refusal:

- the recipient's **AVOID COINS** flag, and
- a giver with too much provincial debt.

## A new character refuses coins

A new character's `AVOID` list starts with `!COINS`, so every coin gift bounces without them knowing.

| Command | Does |
| --- | --- |
| `AVOID` | list the flags (`!` means refused) |
| `AVOID COINS` | allow coins |
| `AVOID !COINS` | refuse them again |
| `AVOID ALL` / `AVOID !ALL` | allow or refuse every flag |

The other flags (JOINING, DRAGGING, HOLDING, TEACHING, WHISPERING, DANCING, TOUCHING) work the same way.

## Debt

The province lends when you cannot pay a fee (a stat trainer, a fine). INFO shows it under Debt.

```
;debt              what you carry and owe (spends nothing)
;debt pay          fetch the shortfall from the teller, PAY ALL at the debt office, walk back
```

Debt offices carry the map's `debt` tag; Zoluren's are in the Crossing's Town Hall and Leth Deriel. Neither WITHDRAW nor PAY costs roundtime.

Carried coins weigh and are lost on death, so bank a hunt's takings (`;bank`).

## Vault rent on a Premium account

Rent is 5 gold Kronars per 30 days at a Carousel Square desk, but on a Premium account `PAY RENT` is waived and still credits the month. VAULT TIME and VAULT STANDARD are free remote reads there. The wiki does not state the waiver.

## Asking for help

Empaths heal for a sentence said aloud in their guild's courtyard; see [healing.md](healing.md).
