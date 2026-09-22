"""The taskbar button's jump list on Windows: right-click the pinned or
running Revenant button and launch another character (#226).

Tasks: "Pick a character..." (the launcher's --pick, the Start Menu
shortcut's mode) and one per character played — the cached roster's
names that have a history.db snapshot, most recently played first, the
whole roster when none has one, twelve at most (a menu of thirty-two
is no shortcut) — each `revenant <Name>`: that character's window if
their session runs, a fresh session otherwise. They are registered once at GUI start through
the shell's ICustomDestinationList under the AppUserModelID the window
claims (APP_USER_MODEL_ID, the one tools/install_shortcut.ps1 stamps on
the shortcut), so the tasks land on our button and not on pythonw's. A
failure anywhere is logged and ignored: the jump list is a convenience.

PyQt6 has no jump-list API (QtWinExtras went with Qt 5) and the venv
has neither pywin32 nor comtypes, so `_register` is a ctypes shim over
four shell interfaces called by vtable slot: ICustomDestinationList,
IObjectCollection, IShellLinkW and IPropertyStore (a task's title is the
link's System.Title property, not its description — that is the
tooltip). From source a task runs the base interpreter's real pythonw
on tools/desktop.py, as the shortcut does (the venv's pythonw is a uv
trampoline that conjures a console); in the packaged build it runs the
executable itself, whose default role is the launcher.
"""

import logging
import sqlite3
import subprocess
import sys
from pathlib import Path

from client.engine.login import load_login_defaults
from client.engine.procspawn import frozen
from client.engine.roster import cached_characters
from client.game.history import database_path

# Windows groups taskbar buttons by AppUserModelID, defaulting to the exe
# path — which for us is pythonw.exe, shared with every other Python GUI.
# Claiming our own ID (matching the one tools/install_shortcut.ps1 stamps
# on the Start Menu shortcut) merges the running window with the pinned
# icon instead of splitting into two buttons.
APP_USER_MODEL_ID = "revenant.client"

REPO = Path(__file__).resolve().parents[3]
DESKTOP_ENTRY = REPO / "tools" / "desktop.py"
ICON = Path(__file__).with_name("revenant.ico")
PICK_TITLE = "Pick a character..."
MAX_CHARACTER_TASKS = 12

log = logging.getLogger(__name__)


def launcher_argv():
    """The argv prefix a task runs the launcher with: the packaged
    executable alone (its default role is the launcher), or from source
    the base interpreter's windowless pythonw on tools/desktop.py —
    falling back to this interpreter and `-m client.engine.launch` when
    either is missing (a venv laid out differently)."""
    if frozen():
        return [sys.executable]
    base = Path(getattr(sys, "_base_executable", None) or sys.executable)
    pythonw = base.with_name("pythonw.exe")
    if pythonw.exists() and DESKTOP_ENTRY.exists():
        return [str(pythonw), str(DESKTOP_ENTRY)]
    return [sys.executable, "-m", "client.engine.launch"]


def played_characters(path=None):
    """The names with a `;sheet` snapshot in history.db, most recently
    snapshotted first — the characters actually played. [] without a
    database or a character table (a fresh install)."""
    try:
        with sqlite3.connect(str(path or database_path())) as db:
            rows = db.execute(
                "SELECT character_name, MAX(logged_at) AS last FROM character "
                "GROUP BY character_name ORDER BY last DESC"
            ).fetchall()
    except sqlite3.Error:
        return []
    return [str(name) for name, _ in rows if name]


def tasks(defaults, launcher, played=()):
    """The jump list's tasks, in order: the picker, then the characters —
    the cached roster's names among `played`, in its order, or the
    whole roster when none of it has been played, MAX_CHARACTER_TASKS at
    most. Each is {title, exe, arguments, description}; `arguments` is
    one command-line string (Windows quoting), what
    IShellLink.SetArguments takes."""
    exe, *lead = launcher
    entries = [
        {
            "title": PICK_TITLE,
            "exe": exe,
            "arguments": subprocess.list2cmdline([*lead, "--pick"]),
            "description": "Choose a character from the roster and launch it",
        }
    ]
    pairs = cached_characters(defaults)
    by_name = {name.lower(): (account, name) for account, name in pairs}
    chosen = [by_name[p.lower()] for p in played if p.lower() in by_name]
    if not chosen:
        chosen = pairs
    several = len({account for account, _ in pairs}) > 1
    for account, name in chosen[:MAX_CHARACTER_TASKS]:
        entries.append(
            {
                "title": name,
                "exe": exe,
                "arguments": subprocess.list2cmdline([*lead, name]),
                "description": f"Launch {name}"
                + (f" ({account})" if several and account else ""),
            }
        )
    return entries


def install(defaults=None, launcher=None, app_id=APP_USER_MODEL_ID):
    """Register the tasks on this process's taskbar button. True when the
    list was committed; False on any other platform or on any failure,
    which is logged and otherwise ignored."""
    if sys.platform != "win32":
        return False
    try:
        if defaults is None:
            defaults = load_login_defaults()
        entries = tasks(defaults, launcher or launcher_argv(), played_characters())
        icon = (sys.executable, 0) if frozen() else (str(ICON), 0)
        _register(app_id, entries, icon)
    except Exception as error:  # a convenience, never a crash
        log.warning("jump list not registered: %s", error)
        return False
    log.info("jump list registered: %d tasks", len(entries))
    return True


# --- the COM shim -----------------------------------------------------------

CLSID_DESTINATION_LIST = "{77F10CF0-3DB5-4966-B520-B7C54FD35ED6}"
IID_ICUSTOM_DESTINATION_LIST = "{6332DEBF-87B5-4670-90C0-5E57B408A49E}"
CLSID_ENUMERABLE_OBJECT_COLLECTION = "{2D3468C1-36A7-43B6-AC24-D3F02FD9607A}"
IID_IOBJECT_COLLECTION = "{5632B1A4-E38A-400A-928A-D4CD63230295}"
IID_IOBJECT_ARRAY = "{92CA9DCD-5622-4BBA-A805-5E9F541BD8C9}"
CLSID_SHELL_LINK = "{00021401-0000-0000-C000-000000000046}"
IID_ISHELL_LINK_W = "{000214F9-0000-0000-C000-000000000046}"
IID_IPROPERTY_STORE = "{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}"
PKEY_TITLE = ("{F29F85E0-4FF9-1068-AB91-08002B27B3D9}", 2)  # System.Title
VT_LPWSTR = 31
CLSCTX_INPROC_SERVER = 1
COINIT_APARTMENTTHREADED = 2


def _register(app_id, entries, icon):
    """Build the shell links and commit them as the user tasks of the
    destination list for `app_id`. Every call is checked (an HRESULT
    failure raises OSError); the list is aborted on the way out of a
    failure so the shell keeps the previous one."""
    import ctypes
    from ctypes import POINTER, Structure, byref, c_int, c_uint, c_void_p, c_wchar_p

    class GUID(Structure):
        _fields_ = [
            ("data1", ctypes.c_ulong),
            ("data2", ctypes.c_ushort),
            ("data3", ctypes.c_ushort),
            ("data4", ctypes.c_ubyte * 8),
        ]

    class PROPERTYKEY(Structure):
        _fields_ = [("fmtid", GUID), ("pid", ctypes.c_ulong)]

    class PROPVARIANT(Structure):
        # vt and three reserved words, then the union — a pointer here —
        # padded to the real 24 bytes so a copy of the whole struct
        # stays inside our memory.
        _fields_ = [
            ("vt", ctypes.c_ushort),
            ("reserved1", ctypes.c_ushort),
            ("reserved2", ctypes.c_ushort),
            ("reserved3", ctypes.c_ushort),
            ("pwszVal", c_wchar_p),
            ("padding", ctypes.c_ubyte * 8),
        ]

    ole32 = ctypes.oledll.ole32

    def guid(text):
        value = GUID()
        ole32.CLSIDFromString(text, byref(value))
        return value

    def method(obj, index, *argtypes, restype=ctypes.HRESULT):
        vtable = ctypes.cast(obj, POINTER(c_void_p))[0]
        address = ctypes.cast(c_void_p(vtable), POINTER(c_void_p))[index]
        prototype = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)
        return prototype(address)

    def release(obj):
        if obj:
            method(obj, 2, restype=ctypes.c_ulong)(obj)

    def create(clsid, iid):
        obj = c_void_p()
        ole32.CoCreateInstance(
            byref(guid(clsid)), None, CLSCTX_INPROC_SERVER, byref(guid(iid)), byref(obj)
        )
        return obj

    def query(obj, iid):
        out = c_void_p()
        method(obj, 0, POINTER(GUID), POINTER(c_void_p))(
            obj, byref(guid(iid)), byref(out)
        )
        return out

    def shell_link(entry):
        link = create(CLSID_SHELL_LINK, IID_ISHELL_LINK_W)
        try:
            method(link, 20, c_wchar_p)(link, entry["exe"])  # SetPath
            method(link, 11, c_wchar_p)(link, entry["arguments"])  # SetArguments
            method(link, 7, c_wchar_p)(link, entry["description"])  # SetDescription
            method(link, 17, c_wchar_p, c_int)(link, *icon)  # SetIconLocation
            store = query(link, IID_IPROPERTY_STORE)
            try:
                key = PROPERTYKEY(guid(PKEY_TITLE[0]), PKEY_TITLE[1])
                value = PROPVARIANT(vt=VT_LPWSTR, pwszVal=entry["title"])
                method(store, 6, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))(
                    store, byref(key), byref(value)
                )  # SetValue
                method(store, 7)(store)  # Commit
            finally:
                release(store)
        except Exception:
            release(link)
            raise
        return link

    initialized = ctypes.windll.ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    destinations = collection = None
    links = []
    try:
        destinations = create(CLSID_DESTINATION_LIST, IID_ICUSTOM_DESTINATION_LIST)
        method(destinations, 3, c_wchar_p)(destinations, app_id)  # SetAppID
        slots = c_uint()
        removed = c_void_p()
        method(destinations, 4, POINTER(c_uint), POINTER(GUID), POINTER(c_void_p))(
            destinations, byref(slots), byref(guid(IID_IOBJECT_ARRAY)), byref(removed)
        )  # BeginList
        release(removed)
        try:
            collection = create(
                CLSID_ENUMERABLE_OBJECT_COLLECTION, IID_IOBJECT_COLLECTION
            )
            for entry in entries:
                link = shell_link(entry)
                links.append(link)
                method(collection, 5, c_void_p)(collection, link)  # AddObject
            method(destinations, 7, c_void_p)(destinations, collection)  # AddUserTasks
            method(destinations, 8)(destinations)  # CommitList
        except Exception:
            method(destinations, 11)(destinations)  # AbortList
            raise
    finally:
        for link in links:
            release(link)
        release(collection)
        release(destinations)
        if initialized in (0, 1):  # S_OK, S_FALSE: ours to balance
            ctypes.windll.ole32.CoUninitialize()
