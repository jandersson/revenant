# Install a Start Menu shortcut for the Revenant client so it can be
# pinned to the taskbar. Idempotent - rerunning overwrites in place.
#
#   powershell -ExecutionPolicy Bypass -File tools/install_shortcut.ps1
#
# Targets the BASE interpreter's real pythonw.exe (resolved from
# .venv\pyvenv.cfg) running tools\desktop.py: truly windowless. The
# venv's own pythonw.exe is a uv trampoline whose console-subsystem hop
# conjures a terminal behind the GUI - never target it. A real exe
# target is also what makes the shortcut pinnable. The AppUserModelID
# stamped here must match the one the GUI sets at startup
# (client_gui.APP_USER_MODEL_ID), or the pinned icon and the running
# window show up as two separate taskbar buttons.
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$icon = Join-Path $repo "client\client\gui\revenant.ico"
$appId = "revenant.client"

$baseDir = ((Get-Content (Join-Path $repo ".venv\pyvenv.cfg") |
    Where-Object { $_ -match "^home = " }) -replace "^home = ", "").Trim()
$pythonw = Join-Path $baseDir "pythonw.exe"

foreach ($required in @($icon, $pythonw)) {
    if (-not (Test-Path $required)) {
        Write-Error "Missing $required (run `uv sync` / `uv run python tools/make_icon.py` first)"
    }
}

$lnk = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\Revenant.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnk)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "`"$(Join-Path $repo 'tools\desktop.py')`""
$shortcut.WorkingDirectory = $repo
$shortcut.IconLocation = "$icon,0"
$shortcut.Description = "Revenant - DragonRealms client"
$shortcut.Save()

# Stamp System.AppUserModel.ID on the .lnk (WScript.Shell cannot set
# shell properties, so go through IPropertyStore on the ShellLink COM
# object). The GUIDs are fixed Windows constants.
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

[StructLayout(LayoutKind.Sequential, Pack = 4)]
public struct PropertyKey {
    public Guid fmtid;
    public uint pid;
    public PropertyKey(Guid f, uint p) { fmtid = f; pid = p; }
}

[StructLayout(LayoutKind.Explicit)]
public struct PropVariant {
    [FieldOffset(0)] public ushort vt;
    [FieldOffset(8)] public IntPtr pointerValue;
}

[ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPropertyStore {
    void GetCount(out uint count);
    void GetAt(uint index, out PropertyKey key);
    void GetValue(ref PropertyKey key, out PropVariant value);
    void SetValue(ref PropertyKey key, ref PropVariant value);
    void Commit();
}

public static class ShortcutAumid {
    public static void Set(string lnkPath, string appId) {
        Type t = Type.GetTypeFromCLSID(new Guid("00021401-0000-0000-C000-000000000046"));
        object link = Activator.CreateInstance(t);
        try {
            ((IPersistFile)link).Load(lnkPath, 2); // STGM_READWRITE - Commit needs write access
            IPropertyStore store = (IPropertyStore)link;
            PropertyKey key = new PropertyKey(new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), 5);
            PropVariant value = new PropVariant();
            value.vt = 31; // VT_LPWSTR
            value.pointerValue = Marshal.StringToCoTaskMemUni(appId);
            try {
                store.SetValue(ref key, ref value);
                store.Commit();
                ((IPersistFile)link).Save(lnkPath, true);
            } finally {
                Marshal.FreeCoTaskMem(value.pointerValue);
            }
        } finally {
            Marshal.ReleaseComObject(link);
        }
    }
}
"@

[ShortcutAumid]::Set($lnk, $appId)

Write-Host "Created: $lnk"
Write-Host 'Pin it: Start menu -> right-click "Revenant" -> Pin to taskbar.'
