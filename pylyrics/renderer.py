"""Unicode-aware typewriter animation and terminal rendering for PyLyrics."""

from __future__ import annotations

import sys
import time
import unicodedata
from typing import Callable, TextIO

from pylyrics.colors import Styler, enable_windows_virtual_terminal
from pylyrics.parser import LyricLine, LyricsDocument

ZWJ = "\u200d"
ZWNJ = "\u200c"
SINHALA_AL_LAKUNA = "\u0dca"  # Sinhala sign al-lakuna (virama)


def _is_combining_or_modifier(ch: str) -> bool:
    """Return True if `ch` is a Unicode combining mark, modifier, or variation selector."""
    if not ch:
        return False
    if ch in (ZWJ, ZWNJ):
        return True
    cat = unicodedata.category(ch)
    if cat in ("Mn", "Mc", "Me"):
        return True
    if unicodedata.combining(ch) > 0:
        return True
    cp = ord(ch)
    # Variation selectors (FE00..FE0F, E0100..E01EF)
    if 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:
        return True
    return False


def _is_virama(ch: str) -> bool:
    """Return True if `ch` is a Sinhala or Indic virama / halant."""
    if not ch:
        return False
    if ch == SINHALA_AL_LAKUNA:
        return True
    # Canonical combining class 9 is Virama in Unicode
    return unicodedata.combining(ch) == 9


def segment_graphemes(text: str) -> list[str]:
    """Segment a string into user-perceived Unicode grapheme clusters.

    Implemented using Python's standard-library `unicodedata` module without external
    dependencies:
    - Keeps base characters attached to all trailing combining marks (`Mn`, `Mc`, `Me`),
      including Sinhala vowel signs (pilla), anusvara, visarga, and al-lakuna (`්`).
    - Keeps Zero Width Joiner (`U+200D`) and Zero Width Non-Joiner (`U+200C`) sequences
      together with the following base consonant and its combining marks so Sinhala
      conjuncts (such as Yansaya `්\u200dය`, Rakaransaya `්\u200dර`, and Repaya) are never
      split mid-animation.
    - Treats `\r\n` as a single cluster if present.
    """
    if not text:
        return []

    clusters: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # Handle CRLF as a single cluster
        if ch == "\r" and i + 1 < n and text[i + 1] == "\n":
            clusters.append("\r\n")
            i += 2
            continue

        cluster_chars = [ch]
        i += 1

        while i < n:
            next_ch = text[i]
            prev_ch = cluster_chars[-1]

            # Attach combining marks, spacing marks, enclosing marks, ZWJ, ZWNJ
            if _is_combining_or_modifier(next_ch):
                cluster_chars.append(next_ch)
                i += 1
                continue

            # If the previous character was ZWJ (e.g. Sinhala Virama + ZWJ + Consonant,
            # or emoji ZWJ sequence), attach the following base character to this cluster
            if prev_ch == ZWJ:
                cluster_chars.append(next_ch)
                i += 1
                continue

            # If the previous character was a Virama immediately followed by ZWJ, the
            # first branch already attached ZWJ and the second branch attaches the base.
            # Also handle cases where ZWNJ/ZWJ precedes a combining sequence.
            if _is_virama(prev_ch) and next_ch in (ZWJ, ZWNJ):
                cluster_chars.append(next_ch)
                i += 1
                continue

            break

        clusters.append("".join(cluster_chars))

    return clusters


def clear_terminal(stream: TextIO | None = None) -> None:
    """Clear the terminal screen and move cursor to the home position using ANSI escapes.

    Avoids spawning shell subprocesses (`cls` / `clear`).
    """
    target = stream if stream is not None else sys.stdout
    enable_windows_virtual_terminal()
    # \033[2J clears visible screen, \033[3J clears scrollback buffer where supported,
    # \033[H moves cursor to top-left (row 1, col 1).
    target.write("\033[2J\033[3J\033[H")
    target.flush()


def render_line_animated(
    text: str,
    styler: Styler,
    char_delay: float = 0.045,
    indent: str = "  ",
    stream: TextIO | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    """Render a single lyric line progressively on the same terminal line.

    Color escape codes are emitted once at the start and end of the line so that
    ANSI sequences never interfere with character-by-character output.
    """
    target = stream if stream is not None else sys.stdout

    if not text:
        target.write("\n")
        target.flush()
        return

    if char_delay <= 0.0:
        target.write(f"{indent}{styler.lyric(text)}\n")
        target.flush()
        return

    clusters = segment_graphemes(text)
    target.write(indent)
    if styler.lyric_prefix:
        target.write(styler.lyric_prefix)

    try:
        for idx, cluster in enumerate(clusters):
            target.write(cluster)
            target.flush()
            if idx < len(clusters) - 1:
                sleep_fn(char_delay)
            else:
                # Brief delay after final character so typing speed feels natural
                sleep_fn(char_delay)
    finally:
        if styler.reset_suffix:
            target.write(styler.reset_suffix)
        target.write("\n")
        target.flush()


def render_document(
    document: LyricsDocument,
    styler: Styler,
    char_delay: float = 0.045,
    line_pause: float = 0.75,
    stream: TextIO | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock_fn: Callable[[], float] = time.monotonic,
    clear_screen: bool = True,
    show_footer: bool = True,
) -> bool:
    """Render a full LyricsDocument (TXT or LRC) to the terminal.

    Overlap policy for LRC files:
    - Each lyric event is scheduled at `session_start + line.timestamp` using a monotonic clock.
    - If a line finishes animating before the next line's timestamp, the renderer sleeps for
      the remaining interval (`target_time - current_time`).
    - If a long line or slow typing speed causes a line to finish *after* the next timestamp
      has already arrived (`current_time >= target_time`), the next line begins immediately
      without skipping any lyrics and without truncating character animation. Subsequent lines
      remain anchored to `session_start` so timing catches up naturally without cumulative drift.

    Returns True if playback completed normally, or False if interrupted by KeyboardInterrupt.
    """
    target = stream if stream is not None else sys.stdout

    if clear_screen:
        clear_terminal(target)

    # Minimal header
    target.write("\n")
    target.write(f"  {styler.title(document.title)}\n")
    artist = document.metadata.get("ar", "").strip()
    if artist:
        target.write(f"  {styler.secondary(artist)}\n")
    target.write("\n")
    target.flush()

    try:
        if document.file_format == "lrc":
            _render_lrc_lines(
                lines=document.lines,
                styler=styler,
                char_delay=char_delay,
                stream=target,
                sleep_fn=sleep_fn,
                clock_fn=clock_fn,
            )
        else:
            _render_txt_lines(
                lines=document.lines,
                styler=styler,
                char_delay=char_delay,
                line_pause=line_pause,
                stream=target,
                sleep_fn=sleep_fn,
            )
    except KeyboardInterrupt:
        target.write("\n")
        target.write(f"  {styler.secondary('— playback interrupted —')}\n")
        target.flush()
        return False

    if show_footer:
        target.write("\n")
        target.write(f"  {styler.secondary('— end of lyrics —')}\n")
        target.flush()

    return True


def _render_txt_lines(
    lines: list[LyricLine],
    styler: Styler,
    char_delay: float,
    line_pause: float,
    stream: TextIO,
    sleep_fn: Callable[[float], None],
) -> None:
    """Render plain TXT lines sequentially with configured pause between lines."""
    total = len(lines)
    for idx, line in enumerate(lines):
        render_line_animated(
            text=line.text,
            styler=styler,
            char_delay=char_delay,
            stream=stream,
            sleep_fn=sleep_fn,
        )
        if idx < total - 1 and line_pause > 0.0:
            sleep_fn(line_pause)


def _render_lrc_lines(
    lines: list[LyricLine],
    styler: Styler,
    char_delay: float,
    stream: TextIO,
    sleep_fn: Callable[[float], None],
    clock_fn: Callable[[], float],
) -> None:
    """Render timestamped LRC lines anchored to a monotonic session start time."""
    session_start = clock_fn()
    for line in lines:
        target_offset = line.timestamp if line.timestamp is not None else 0.0
        elapsed = clock_fn() - session_start
        wait_seconds = target_offset - elapsed
        if wait_seconds > 0.0:
            sleep_fn(wait_seconds)

        render_line_animated(
            text=line.text,
            styler=styler,
            char_delay=char_delay,
            stream=stream,
            sleep_fn=sleep_fn,
        )
