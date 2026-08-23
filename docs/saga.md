# Saga, the new official front end — what it means here

Saga changes nothing about the wire protocol revenant speaks today:
it is a new official client over the same Stormfront/Wrayth XML
stream, and the eaccess login handshake shows no sign of changing.
The two things to actually watch are (1) new XML emissions the game
is growing alongside Saga (maps, combat panel, party) — capture and
pin them as they appear — and (2) Saga's inverted Lich launch model,
which sketches what a "raw-XML attach" mode for our session could
offer. Researched 2026-08-23 (#83); Saga is in open beta and moving
fast, so re-verify before relying on details.

## What Saga is

Simutronics' new official front end for DragonRealms and GemStone IV,
by GM Auchand and GM Nyxus, announced at SimuCon July 2026, open beta
since 2026-08-12. Electron-based; Windows/Mac/Linux now, a lighter
web client (and mobile via it) planned. Wrayth is not deprecated;
only the old WebFE will be replaced. Free with a subscription.

Feature highlights (from the community FAQ): a GM-built auto-mapper
with click-to-travel and a TRAVEL verb, panel/layout system with
themes, Wrayth-language scripting ("100% portable over from
Wrayth"), triggers, combat/party panels, inventory and experience
panels, cloud-stored per-character settings. Heavy: 0.5–1.4GB per
instance.

## The issue's questions, answered

**Does the wire protocol change?** No — Saga consumes the same XML
feed every Stormfront-family client does ("Lich can access the XML
feed as in previous front ends"). But the game's XML itself is being
extended alongside Saga: GM Nyxus confirms XML updates "as needed",
and maps, combat panels, and party features "leverage updated XML
emissions". Those emissions ride the same stream we parse, so new
tags will eventually reach `xml_data.py` regardless of front end.
The parser ignores tags it doesn't know and routes unknown streams
to the main window, so the failure mode is cosmetic noise, not a
crash — still, capture the new tags as they surface and pin them as
fixtures (#98).

**What does "Lich-able" mean concretely?** Two things, per the
lich-5 source (which shipped first-class support):

- `--saga` is a frontend flag beside `--stormfront`/`--avalon`/
  `--frostbite`: lich treats Saga as an XML-stream front end and
  relays the stream unconverted (their 5.19.0 bug "GSL output sent
  to XML frontends" confirms the taxonomy).
- The launch model inverts. Classic lich launches the front end and
  plays man-in-the-middle; with Saga, *Saga owns authentication and
  starts the Lich process itself*. Lich's CLI hands off via an
  undocumented startup contract (Saga 0.8.5): `SAGA_AUTO_LOGIN=
  Char@CODE`, `SAGA_AUTO_LOGIN_ACCOUNT`, `SAGA_AUTO_LOGIN_MODE=lich`
  environment variables, no game key passed. GM Auchand: "We have
  the capability currently to allow access to other clients from
  within Saga."

**eaccess handshake?** No evidence of change: lich's login flow is
untouched apart from the optional Saga handoff, and Saga's own
"direct client login" is an in-client credential flow like Wrayth's.
Our `login.py` model stands; keep the captures current.

**Anything revenant could attach to, or offer?** Saga attaches to a
localhost socket that speaks the game's raw XML (that is how it sits
downstream of lich). Our session serves JSON-lines frames instead,
so Saga cannot attach to a revenant session today — a raw-XML relay
mode would change that and make every XML-speaking front end (Saga,
Wrayth, Avalon) a potential revenant frontend (#99).

## Does Saga change what's worth building here?

Mostly no; it sharpens what is ours:

- **Mapper**: Saga's GM-built auto-map with click-to-travel overlaps
  the Map dock + ;go2. Theirs is official and richer visually; ours
  is scriptable (walker as an engine for ;favors, ;athletics) and
  danger-aware (#79). Both ride the same community/game map ideas —
  no reason to stop.
- **Scripting**: Saga stays on the Wrayth trigger/script language;
  our Python engine with threads, state access, and a package
  ecosystem is a different class of tool. No convergence.
- **Session model**: nothing in Saga detaches — one game connection
  per client, reconnect-on-drop only. The detachable session,
  ;reexec, and multi-frontend attach remain revenant-only.
- **Analytics**: xp history/beholder have no Saga counterpart beyond
  an in-client experience panel.

## Sources

- Community FAQ (Darcena & Tysong, from SimuCon panels + Discord):
  <https://tinyurl.com/3rys22vt>
- TownCrier announcement and beta posts:
  <https://gstowncrier.com/news/saga-the-new-front-end-coming-to-simutronics/>,
  <https://gstowncrier.com/news/saga-beta-is-here/>,
  <https://gstowncrier.com/news/the-saga-front-end-faq/>
- Elanthipedia front-end roster: <https://drwiki.play.net/Front_end>
- lich-5 source (Saga launch contract, frontend taxonomy):
  <https://github.com/elanthia-online/lich-5>
- The official page <https://www.play.net/dr/play/saga-info.asp>
  returned HTTP 500 on both research days; retry later.
