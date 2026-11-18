"""Автозапуск вместе с Windows (HKCU\\...\\Run)."""
import sys
from pathlib import Path

from .constants import APP_NAME, IS_WINDOWS, is_frozen

_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _command() -> str:
    if is_frozen():
        return f'"{sys.executable}" --minimized'
    main = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{sys.executable}" "{main}" --minimized'


def is_enabled() -> bool:
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return False


def set_enabled(on: bool) -> None:
    if not IS_WINDOWS:
        return
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        pass
