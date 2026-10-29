"""ANSI true-color themes and terminal styling utilities for PyLyrics."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import TextIO

RESET = "\033[0m"


def _rgb_fg(hex_color: str) -> str:
    """Convert a #RRGGBB hex string into an ANSI true-color foreground escape sequence."""
    cleaned = hex_color.lstrip("#")
    if len(cleaned) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    r = int(cleaned[0:2], 16)
    g = int(cleaned[2:4], 16)
    b = int(cleaned[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m"


@dataclass(frozen=True)
class ThemePalette:
    """Color palette definition for a restrained terminal theme.

    Never forces a background color; relies on the terminal's native background.
    """

    name: str
    display_name: str
    description: str
    accent_hex: str
    lyrics_hex: str
    secondary_hex: str
    highlight_hex: str
    warning_hex: str
    error_hex: str

    @property
    def accent(self) -> str:
        return _rgb_fg(self.accent_hex)

    @property
    def lyrics(self) -> str:
        return _rgb_fg(self.lyrics_hex)

    @property
    def secondary(self) -> str:
        return _rgb_fg(self.secondary_hex)

    @property
    def highlight(self) -> str:
        return _rgb_fg(self.highlight_hex)

    @property
    def warning(self) -> str:
        return _rgb_fg(self.warning_hex)

    @property
    def error(self) -> str:
        return _rgb_fg(self.error_hex)


THEMES: dict[str, ThemePalette] = {
    "lavender": ThemePalette(
        name="lavender",
        display_name="Lavender",
        description="Muted lavender accents, warm ivory lyrics, neutral gray secondary text",
        accent_hex="#B7A4D4",
        lyrics_hex="#EEEAF3",
        secondary_hex="#8D929B",
        highlight_hex="#D6B58B",
        warning_hex="#D6B58B",
        error_hex="#D98A8A",
    ),
    "sage": ThemePalette(
        name="sage",
        display_name="Sage",
        description="Subdued sage-green accents, soft off-white lyrics, neutral gray secondary text",
        accent_hex="#9AB8A2",
        lyrics_hex="#EFF2EE",
        secondary_hex="#8C948E",
        highlight_hex="#C8B88A",
        warning_hex="#C8B88A",
        error_hex="#D98A8A",
    ),
    "amber": ThemePalette(
        name="amber",
        display_name="Amber",
        description="Warm amber accents, ivory lyrics, muted gray secondary text",
        accent_hex="#D4A359",
        lyrics_hex="#F5EFE6",
        secondary_hex="#948E86",
        highlight_hex="#E0B97D",
        warning_hex="#E0B97D",
        error_hex="#D9847A",
    ),
    "monochrome": ThemePalette(
        name="monochrome",
        display_name="Monochrome",
        description="White, gray, and muted neutral tones",
        accent_hex="#D4D4D4",
        lyrics_hex="#F2F2F2",
        secondary_hex="#8A8A8A",
        highlight_hex="#BDBDBD",
        warning_hex="#B0B0B0",
        error_hex="#C8C8C8",
    ),
}

DEFAULT_THEME = "lavender"


def enable_windows_virtual_terminal() -> bool:
    """Enable ANSI escape sequence processing on Windows consoles if applicable."""
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE = -11
        if handle in (0, -1):
            return False
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        enable_vt = 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        if not (mode.value & enable_vt):
            if not kernel32.SetConsoleMode(handle, mode.value | enable_vt):
                return False
        return True
    except Exception:
        return False


def supports_color(stream: TextIO | None = None) -> bool:
    """Return True if the environment and output stream likely support ANSI colors."""
    if os.environ.get("NO_COLOR") is not None:
        return False
    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False
    target = stream if stream is not None else sys.stdout
    is_tty = getattr(target, "isatty", lambda: False)()
    if not is_tty:
        return False
    if os.name == "nt":
        return enable_windows_virtual_terminal()
    return True


def get_theme(theme_name: str) -> ThemePalette:
    """Look up a theme by name (case-insensitive), falling back to Lavender."""
    normalized = (theme_name or "").strip().lower()
    return THEMES.get(normalized, THEMES[DEFAULT_THEME])


class Styler:
    """Applies consistent theme colors to terminal text with graceful fallback."""

    def __init__(self, theme_name: str = DEFAULT_THEME, color_enabled: bool = True) -> None:
        self.palette: ThemePalette = get_theme(theme_name)
        self.color_enabled: bool = bool(color_enabled)

    def _wrap(self, code: str, text: str) -> str:
        if not self.color_enabled or not text:
            return text
        return f"{code}{text}{RESET}"

    def title(self, text: str) -> str:
        """Style the application title and banner border."""
        return self._wrap(self.palette.accent, text)

    def heading(self, text: str) -> str:
        """Style section and menu headings."""
        return self._wrap(self.palette.accent, text)

    def highlight(self, text: str) -> str:
        """Style selected values, option keys, and highlights."""
        return self._wrap(self.palette.highlight, text)

    def lyric(self, text: str) -> str:
        """Style primary lyric text."""
        return self._wrap(self.palette.lyrics, text)

    def secondary(self, text: str) -> str:
        """Style secondary labels, metadata, and subtle status prompts."""
        return self._wrap(self.palette.secondary, text)

    def warning(self, text: str) -> str:
        """Style non-fatal warnings."""
        return self._wrap(self.palette.warning, text)

    def error(self, text: str) -> str:
        """Style error messages."""
        return self._wrap(self.palette.error, text)

    @property
    def lyric_prefix(self) -> str:
        """ANSI escape sequence to start lyric line coloring without per-character escapes."""
        return self.palette.lyrics if self.color_enabled else ""

    @property
    def reset_suffix(self) -> str:
        """ANSI escape sequence to reset coloring at the end of a line."""
        return RESET if self.color_enabled else ""
