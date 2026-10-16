---
name: pixel-art
description: Draw a DragonRealms scene as SNES/JRPG-style pixel art from the game's own words — the room description, LOOK at your character, at the NPCs and at the other characters there — rendered with the skill's pixelart.py helper, optionally under a JRPG dialogue box, and saved to the operator's vault. Use whenever the operator asks for a picture, image, drawing or pixel art of a place, a moment or the characters in the game.
---

# Pixel art of a scene

A picture here is built from what the game says, not from guesses: the
room's description and listing, and a LOOK at every figure in it. The
sprites are small, so the job is choosing the few details that read at
12 pixels wide.

## 1. Gather the scene (read-only, nothing acts)

1. **The room:** `uv run revenant-send --origin claude --character NAME --state room`
   gives the title, description and exits with nothing sent; a LOOK
   adds the full "You also see ..." listing (items in the room's order)
   and "Also here:".
2. **Your character:** `LOOK <first name>` (e.g. `look lanival`) — race,
   face, eyes, hair, beard, skin, build, then everything worn.
3. **Each NPC:** `LOOK <noun>` (`look appraiser`, `look clerk`) — the
   game's own sketch of them, often a tool or garment that defines them.
4. **Each other character:** `LOOK <name>` once — race, hair, age,
   what they hold and wear. Another player shows in the picture only if
   the operator wants them there.
5. **The objects that matter:** `LOOK <thing>` for the few the scene is
   about (a kiosk, a ferry's chain, a statue).

Each LOOK echoes as `>> [claude] ...` in the operator's window: one per
figure, sent through `--answer 3`, never a loop. Elanthipedia
(`uv run python tools/wiki.py "<Title>"`) fills in a race's or an NPC's
look when the game is terse.

## 2. Pick what a sprite can carry

From each LOOK keep three to five things, the ones visible from across
a room:

- race and build (an Elothean is slight, a Dwarf compact, a Gor'Tog huge);
- hair, beard and skin colour; age ("archaic" reads as white hair);
- the outermost layer: a hat or helm, a coat, robe or armour, a cloak;
- what is in the hands, and one carried thing with a silhouette (a staff,
  a bow, a shield);
- one signature detail (an appraiser's lens headband, a glowing tessera).

Drop jewellery, pouches and the rest of the inventory list.

## 3. Draw

Write a scene script beside the art and import the helper:

```python
import sys
sys.path.insert(0, r"<repo>/.claude/skills/pixel-art")
from pixelart import Canvas

c = Canvas(192, 120, "#140c1e")
...
c.save("place-pixel.png")                                          # the still
c.save("place-pixel-dialogue.png", speaker="KIOSK", text="Partial acquisition\nauthorized.")
```

Run it with `uv run --no-project --with pillow python scene.py`.

- **Frame:** 192×120, saved at 5×. A 3/4 top-down interior the way SNES
  RPGs draw one: the back wall in the top third, the floor below, objects
  standing on it with a 2-pixel shadow under each.
- **Sprites:** about 12×22 pixels, head a third of the height; two pixels
  of eye, a row of mouth. Characters stand in front, facing what they do.
- **Palette:** a few colours per object, a light and a dark of each; light
  sources as `glow()` rings; white single-pixel glints on glass and gems.
- **Dialogue:** a short line the game itself said in the moment, about 28
  characters a line (the bitmap font is 6 pixels a character); `\n` breaks it.

## 4. Check and deliver

1. Read the PNG and look at it: overflowing text, a sprite that does not
   match its LOOK, an object hidden behind another. Fix and render again.
2. Save the still, the dialogue version and the scene script in the
   vault's `Games/DragonRealms/Art/` folder (the vault in the operator's
   global instructions), named after the place.
3. Add a section to `Games/DragonRealms/Art.md`: the place, what the
   picture shows and from which descriptions, the image embedded.
4. Send the image with SendUserFile (`display: render`) and log a line in
   the daily note.

Art stays in the vault, never in the repo: it shows the operator's
characters and other players by name.
