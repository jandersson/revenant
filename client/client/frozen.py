"""The packaged build's single entry point: one executable, several roles.

    Revenant.exe                       the launcher (window + session)
    Revenant.exe --role client.session --port 4242 ...
    revenant-cli.exe --role client.tui Lanival
    revenant-cli.exe --role client.sendcmd exp all

An installed copy (#60) has no Python on the path, so the launcher,
the session it spawns, the dashboard the session autostarts, and the
Windows ;reexec child all run as this executable with a role; the
spawn sites build their argv through client/procspawn.command_for,
which chooses `-m module` from source and `--role module` here.
Without --role the launcher runs.
"""

import importlib
import inspect
import sys

ROLES = {
    "client.launch": "client.launch",
    "client.session": "client.session",
    "beholder.app": "beholder.app",
    "client.gui.chat_window": "client.gui.chat_window",
    "client.tui": "client.tui",
    "client.sendcmd": "client.sendcmd",
}
DEFAULT_ROLE = "client.launch"


def split_role(argv):
    """(role, remaining argv): `--role X` leads, or the launcher."""
    if len(argv) >= 2 and argv[0] == "--role":
        return argv[1], list(argv[2:])
    return DEFAULT_ROLE, list(argv)


def run(role, argv):
    """Import the role's module and call its main with argv, in the
    module's own convention: main(argv) when it takes one, else
    sys.argv is set and main() called."""
    module_name = ROLES.get(role)
    if module_name is None:
        print(
            f"revenant: unknown role {role!r}; one of {', '.join(ROLES)}",
            file=sys.stderr,
        )
        return 2
    module = importlib.import_module(module_name)
    main = module.main
    if inspect.signature(main).parameters:
        return main(argv)
    sys.argv = [sys.argv[0], *argv]
    return main()


def main(argv=None):
    role, rest = split_role(sys.argv[1:] if argv is None else list(argv))
    result = run(role, rest)
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    sys.exit(main())
