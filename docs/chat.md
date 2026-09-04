# LNet chat

Revenant talks to LNet, the Lich project's chat server, two ways: a standalone window (`revenant-chat`) and `;lnet` inside the game window. Both share one library, `chat/`, and one rule.

> **LNet's rule: only log in as a character who is in the game right now.** Being on LNet as a character who is not logged into DragonRealms is a bannable offence there. The standalone window makes it easy to forget, so open it only while that character is playing, and close it when they log out.

## The standalone window

```sh
uv run revenant-chat            # pick one of your characters
uv run revenant-chat Lanival    # or name one
```

Only names from your cached roster (the same list the game picker uses) are offered or accepted: LNet names are character names. The last name used is remembered.

Plain typing goes to your default channel. The commands work with or without a leading `;`:

| Typed | Does |
| --- | --- |
| `chat <msg>` or plain text | send to your default channel |
| `chat on <channel> <msg>` (or `chat :<channel> <msg>`) | send to a channel |
| `chat to <name> <msg>` (or `chat ::<name> <msg>`) | private message |
| `reply <msg>` | answer the last private message |
| `who [name]` | who is connected |
| `stats` | server statistics |
| `channels [all]` | list channels (top 15, or all) |
| `tune <channel>` / `untune <channel>` | manage channel subscriptions |

Ctrl+R reconnects; Ctrl+Q quits.

## Inside the game window: `;lnet`

`;lnet` brings the same chat into the Thoughts dock, lich-style (`[Channel]-Name: "msg"`, `[Private]-Name` for tells, `[PrivateTo]-Name` for your own). The classic commands are the table above with a `;` in front, and `;chat` starts the connection on demand. `;help lnet` is the manual; `;stop lnet` disconnects. Identity is the character the session is playing (`LNET_NAME` overrides).

Replies to `;who`, `;stats` and `;channels` arrive as Ruby Marshal, the serialisation Lich reads natively, and render through `chat/rmarshal.py`.

## Passwords

LNet names can be password-protected on the server. If a name is protected, login must carry the password or the server answers `password required` and disconnects.

- The durable place is the OS keychain, service `revenant-lnet`, one entry per name. The window fills it in when a login is rejected: it asks once, with a "remember" checkbox. From a terminal: `keyring set revenant-lnet <Name>`.
- `LNET_PASSWORD` overrides for one run.
- The git-ignored `chat/lnet_password.txt` is a legacy fallback from before the keychain. Never commit a password.

To protect a name (or change its password), log in and call `Server.register_password("...")`; the literal string `"nil"` removes protection. Forgotten passwords are reset at <https://lnet.lichproject.org>.

## Logs

Every connection keeps an append-only traffic log beside the game logs, `~/.revenant/logs/lnet-<stamp>.log`: every element sent and every chunk received, timestamped, the login's password redacted. It is how a message that renders oddly gets diagnosed after the fact.

## Under the hood

`chat/chat.py` is a minimal LNet client in pure Python (stdlib `ssl` only). It connects to `lnet.lichproject.org:7155`, verifies the server against the pinned CA in `chat/LnetCert.txt` plus the `lichproject.org`/`LichNet` common-name check the reference client uses, sends the login element, answers pings, and parses the incoming XML stream into typed messages. The protocol notes follow `lnet.lic` 1.15; the module began as a rough port of rcuhljr's Genie LNet plugin (see [bibliography.md](bibliography.md)). `chat/commands.py` holds the command grammar the window and the script share. `LNET_DEBUG` set to anything prints raw protocol to stdout.
