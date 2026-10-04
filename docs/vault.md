# The vault

`;vault` walks to your Carousel, puts items in your vault or takes them out, and comes back out.

```
;vault put leather compendium, fine scroll    store each item
;vault get leather compendium                 take it out and stow it
;vault list                                   what the vault holds
;vault put map back                           any verb, then walk back
```

- Name an item by adjective and noun ("leather compendium"); a bare noun takes the first item of it.
- The profile's `vault` is the Carousel your vault is at (a `;go2` target, the Crossing's is 8285); empty walks to the nearest town's.
- An item comes back out of the vault under a new id.
- Rent is 5,000 Kronars a month, paid at the Carousel's desk; `;vault` does not pay it.
