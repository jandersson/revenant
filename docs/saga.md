# Saga

Saga, Simutronics' new official front end, changes nothing revenant depends on: it reads the same XML stream, and the login handshake is unchanged. Saga is in beta and moving fast; re-check before relying on details.

## What it is

- An Electron client for DragonRealms and GemStone IV, free with a subscription; a web client is planned.
- Features: a GM-built auto-mapper with click-to-travel, panels and themes, Wrayth-language scripting and triggers, combat, party, inventory and experience panels.
- Wrayth stays; only the old web front end is replaced.

## What to watch

- **New XML.** The game is growing new emissions alongside Saga (maps, combat panel, party). They arrive on the stream we parse. The parser ignores unknown tags, so the failure is noise, not a crash — capture them and pin them as fixtures.
- **Lich's inverted launch.** With Saga, Saga logs in and starts Lich, which relays the raw XML to it over a localhost socket. Our session speaks JSON frames, so Saga cannot attach to it; a raw-XML relay mode would let Saga, Wrayth or Avalon attach.

## Should revenant identify as Saga?

Not by default. The login sends `/FE:STORMFRONT`, and every capture is pinned to that stream; Lich still sends `/FE:WRAYTH` even with Saga attached. The experiment: capture a native Saga session's handshake and first minutes, diff it against ours, and if it earns more (map data, party, timers), make the identity a setting with Stormfront as the default.

## What stays ours

- **Map:** Saga's mapper is prettier; ours is scriptable (`;go2`, the walker under every script).
- **Scripting:** Wrayth triggers versus Python threads with the parser's state.
- **Sessions:** nothing in Saga detaches; the detachable session, `;reexec` and several windows per character stay revenant's.
- **History:** beholder has no Saga counterpart.

## Sources

- Community FAQ: <https://tinyurl.com/3rys22vt>
- lich-5 (the Saga launch contract): <https://github.com/elanthia-online/lich-5>
- Elanthipedia's front-end list: <https://drwiki.play.net/Front_end>
