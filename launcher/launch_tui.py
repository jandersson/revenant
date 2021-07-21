import socket
from subprocess import Popen, run
from pathlib import Path
from time import sleep
from contextlib import closing

import urwid

choices = "Hotdog Crannach".split()

profanity_log_dir = Path("/tmp/")
if not profanity_log_dir.exists():
    raise FileNotFoundError("Logging directory does not exist")


def launch_lich(lich_path: Path, lich_args):
    lich_args.insert(0, str(lich_path))
    Popen(lich_args)


def launch_profanity(profanity_path, profanity_args=[]):
    profanity_args.insert(0, str(profanity_path))
    run(profanity_args)


def get_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def menu(title, choices):
    body = [urwid.Text(title), urwid.Divider()]
    for c in choices:
        button = urwid.Button(c)
        urwid.connect_signal(button, "click", item_chosen, c)
        body.append(urwid.AttrMap(button, None, focus_map="reversed"))
    return urwid.ListBox(urwid.SimpleFocusListWalker(body))


def item_chosen(button, choice):
    response = urwid.Text(["You chose ", choice, "\n"])
    done = urwid.Button("Launch!")
    urwid.connect_signal(done, "click", launch_dragonrealms, choice)
    main.original_widget = urwid.Filler(
        urwid.Pile([response, urwid.AttrMap(done, None, focus_map="reversed")])
    )


def launch_dragonrealms(button, character):
    headless_port = get_free_port()

    lich_executable = Path("/home/jonas/dragonrealms/lich/lich.rbw")
    if not lich_executable.exists():
        raise FileNotFoundError("Cant find lich executable")

    profanity_executable = Path("/home/jonas/dragonrealms/ProfanityFE/profanity.rb")
    if not profanity_executable.exists():
        raise FileNotFoundError("Cant find profanity executable")

    lich_args = [
        "--login",
        character,
        f"--detachable-client={headless_port}",
        "--without-frontend",
        "--dragonrealms",
    ]

    profanity_args = [
        f"--port={headless_port}",
        f"--log-name={character}",
        f"--log-dir={str(profanity_log_dir)}",
    ]

    launch_lich(lich_executable, lich_args)
    sleep(10)
    urwid.ExitMainLoop()
    launch_profanity(profanity_executable, profanity_args)


main = urwid.Padding(menu("Characters", choices), left=2, right=2)
top = urwid.Overlay(
    main,
    urwid.SolidFill("\N{MEDIUM SHADE}"),
    align="center",
    width=("relative", 60),
    valign="middle",
    height=("relative", 60),
    min_width=20,
    min_height=9,
)
urwid.MainLoop(top, palette=[("reversed", "standout", "")]).run()
