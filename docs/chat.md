# LNet chat

Revenant talks to LNet, the Lich project's chat server, in a standalone window (`revenant-chat`) or in the game window's Thoughts dock (`;lnet`).

> **Only be on LNet as a character who is in the game right now.** Being on LNet as a character who is not logged into DragonRealms is a bannable offence. Open the standalone window only while that character plays, and close it when they log out.

## The standalone window

```sh
uv run revenant-chat            # pick one of your characters
uv run revenant-chat Lanival    # or name one
```

Only names from your character roster are offered. Ctrl+R reconnects; Ctrl+Q quits.

## Commands

The same in both places; in the game window they start with `;`.

| Typed | Does |
| --- | --- |
| `chat <msg>` (or plain text in the window) | send to your default channel |
| `chat on <channel> <msg>` / `chat :<channel> <msg>` | send to a channel |
| `chat to <name> <msg>` / `chat ::<name> <msg>` | private message |
| `reply <msg>` | answer the last private message |
| `who [name]` | who is connected |
| `stats` | server statistics |
| `channels [all]` | list channels |
| `tune <channel>` / `untune <channel>` | subscribe or unsubscribe |

- A name you have heard from this session can be typed without the server's `DR:` prefix or capital.
- In the game window, `;lnet` starts on the first command; `;stop lnet` disconnects. Identity is the character being played. When the server drops the connection, `;lnet` logs in again after 30 s, then 1, 2, 4 and 5 minutes; a rejected login ends it.

## Passwords

A protected name must log in with its password.

- Store it in the OS keychain: File → **LNet Password…** in the game window, the chat window's *remember* box, or `keyring set revenant-lnet <Name>`.
- `LNET_PASSWORD` overrides for one run.
- To protect or change a name's password, log in and call `Server.register_password("...")`; `"nil"` removes it. Forgotten passwords reset at <https://lnet.lichproject.org>.

## Logs and internals

- Every connection logs its traffic to `~/.revenant/logs/lnet-<Name>-<stamp>.log`, password redacted.
- `chat/chat.py` is a stdlib-only LNet client (TLS to `lnet.lichproject.org:7155`, pinned CA); `chat/commands.py` is the grammar both frontends share. `LNET_DEBUG=1` prints the raw protocol.
- Sources: [bibliography.md](bibliography.md).
