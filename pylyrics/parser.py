"""UTF-8 TXT and timestamped LRC file parsing for PyLyrics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_EXTENSIONS = {".txt", ".lrc"}

# Matches [MM:SS.xx] or [MM:SS.xxx] (also supports 1+ digit minutes)
_TIMESTAMP_TAG_RE = re.compile(r"\[(\d{1,3}):(\d{2})\.(\d{2,3})\]")

# Matches metadata tags like [ti:Song Title], [ar:Artist], [al:Album], [by:Creator], [offset:0]
_METADATA_TAG_RE = re.compile(r"^\[([a-zA-Z][a-zA-Z0-9_-]*):(.*)\]\s*$")

# Matches any leading bracketed token [ ... ] to detect malformed tags on a line
_LEADING_BRACKET_RE = re.compile(r"^(\[[^\]]*\])+")

KNOWN_METADATA_KEYS = {
    "ti",
    "ar",
    "al",
    "au",
    "by",
    "length",
    "offset",
    "re",
    "ve",
    "tool",
    "id",
}


class LyricsError(Exception):
    """Raised when a lyrics file cannot be loaded or contains no valid lyrics."""


@dataclass(frozen=True)
class LyricLine:
    """Represents a single lyric line, optionally scheduled at a timestamp (in seconds)."""

    text: str
    timestamp: float | None = None
    line_number: int = 0


@dataclass(frozen=True)
class LyricsDocument:
    """Structured representation of a loaded TXT or LRC file."""

    title: str
    source_path: Path
    file_format: str  # "txt" or "lrc"
    lines: list[LyricLine]
    metadata: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def validate_lyrics_path(file_path: str | Path) -> Path:
    """Validate that a path points to an existing, readable .txt or .lrc file."""
    raw = str(file_path).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1].strip()
    if not raw:
        raise LyricsError("No file path was provided.")

    path = Path(raw).expanduser()
    if not path.exists():
        raise LyricsError(f"File not found: '{path}'")
    if path.is_dir():
        raise LyricsError(f"Path is a directory, not a file: '{path}'")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise LyricsError(
            f"Unsupported file extension '{path.suffix or '(none)'}'. Supported formats: {supported}"
        )
    return path.resolve()


def discover_lyrics_files(directory: str | Path) -> list[Path]:
    """Return a sorted list of .txt and .lrc files inside the given directory."""
    dir_path = Path(directory).expanduser()
    if not dir_path.exists() or not dir_path.is_dir():
        return []
    try:
        files = [
            entry
            for entry in dir_path.iterdir()
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    except OSError:
        return []
    return sorted(files, key=lambda p: (p.name.lower(), p.name))


def read_utf8_file(path: Path) -> str:
    """Read a text file strictly as UTF-8, stripping any UTF-8 BOM (U+FEFF)."""
    try:
        raw_bytes = path.read_bytes()
    except PermissionError as exc:
        raise LyricsError(f"Permission denied when reading '{path.name}'.") from exc
    except OSError as exc:
        raise LyricsError(f"Could not read file '{path.name}': {exc}") from exc

    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LyricsError(
            f"File '{path.name}' is not valid UTF-8 encoded text (invalid byte at position {exc.start})."
        ) from exc

    return text


def parse_txt_content(
    content: str,
    source_path: Path | None = None,
) -> LyricsDocument:
    """Parse plain UTF-8 TXT lyric content.

    Blank-line policy:
    - Leading and trailing blank lines at the very beginning/end of the file are trimmed.
    - Internal blank lines between lyric lines are preserved as empty LyricLine(text="")
      entries so stanza breaks are visually maintained.
    - Files containing only whitespace are rejected with a LyricsError.
    """
    resolved_path = source_path if source_path is not None else Path("lyrics.txt")
    raw_lines = content.splitlines()

    # Find first and last non-empty line indices
    non_empty_indices = [i for i, line in enumerate(raw_lines) if line.strip() != ""]
    if not non_empty_indices:
        raise LyricsError(f"File '{resolved_path.name}' contains no lyrics.")

    first_idx = non_empty_indices[0]
    last_idx = non_empty_indices[-1]

    lines: list[LyricLine] = []
    for idx in range(first_idx, last_idx + 1):
        lines.append(
            LyricLine(
                text=raw_lines[idx],
                timestamp=None,
                line_number=idx + 1,
            )
        )

    return LyricsDocument(
        title=resolved_path.stem,
        source_path=resolved_path,
        file_format="txt",
        lines=lines,
        metadata={},
        warnings=[],
    )


def _parse_timestamp_token(minutes_str: str, seconds_str: str, fraction_str: str) -> float:
    """Convert MM, SS, and centisecond/millisecond strings into total seconds."""
    minutes = int(minutes_str)
    seconds = int(seconds_str)
    if seconds >= 60:
        raise ValueError(f"Seconds out of range (00-59): {seconds_str}")

    if len(fraction_str) == 2:
        fraction = int(fraction_str) / 100.0
    elif len(fraction_str) == 3:
        fraction = int(fraction_str) / 1000.0
    else:
        raise ValueError(f"Unsupported fraction precision: {fraction_str}")

    return round(minutes * 60.0 + seconds + fraction, 3)


def parse_lrc_content(
    content: str,
    source_path: Path | None = None,
) -> LyricsDocument:
    """Parse timestamped LRC content into sorted LyricLine events.

    Policies:
    - Supports [MM:SS.xx] (centiseconds) and [MM:SS.xxx] (milliseconds).
    - Ignores metadata tags such as [ti:], [ar:], [al:], [by:] as lyric events,
      storing them in the document's metadata dictionary.
    - Supports multiple timestamps on a single line, creating one event per timestamp.
    - Sorts events chronologically while preserving original relative order for identical timestamps.
    - Timestamped lines with empty lyric text (e.g. '[00:16.00]') are preserved as empty
      lyric lines (`text=""`) to support timed stanza breaks / instrumental pauses.
    - Malformed lines are skipped with a warning recorded in `document.warnings`.
    """
    resolved_path = source_path if source_path is not None else Path("lyrics.lrc")
    raw_lines = content.splitlines()

    metadata: dict[str, str] = {}
    warnings: list[str] = []
    indexed_events: list[tuple[float, int, LyricLine]] = []
    sequence_counter = 0

    for line_idx, raw_line in enumerate(raw_lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue

        # Check if the entire line is a metadata tag like [ti:Song Title]
        meta_match = _METADATA_TAG_RE.match(stripped)
        if meta_match:
            key = meta_match.group(1).lower()
            val = meta_match.group(2).strip()
            # Ensure it is not actually a timestamp like [00:12.34]
            if not key.isdigit():
                if key in KNOWN_METADATA_KEYS or not _TIMESTAMP_TAG_RE.search(stripped):
                    metadata[key] = val
                    continue

        # Extract all contiguous leading bracket tags
        leading_match = _LEADING_BRACKET_RE.match(stripped)
        if not leading_match:
            warnings.append(f"Line {line_idx}: Ignored untimestamped line.")
            continue

        bracket_prefix = leading_match.group(0)
        lyric_text = stripped[len(bracket_prefix) :]

        # Parse every bracketed token in the prefix
        raw_tags = re.findall(r"\[[^\]]*\]", bracket_prefix)
        line_timestamps: list[float] = []
        had_invalid_tag = False

        for tag in raw_tags:
            ts_match = _TIMESTAMP_TAG_RE.fullmatch(tag)
            if ts_match:
                try:
                    ts_val = _parse_timestamp_token(
                        ts_match.group(1),
                        ts_match.group(2),
                        ts_match.group(3),
                    )
                    line_timestamps.append(ts_val)
                except ValueError as exc:
                    had_invalid_tag = True
                    warnings.append(f"Line {line_idx}: Invalid timestamp '{tag}' ({exc}).")
            else:
                # Could be an inline metadata tag or malformed timestamp
                inner_meta = _METADATA_TAG_RE.match(tag)
                if inner_meta and inner_meta.group(1).lower() in KNOWN_METADATA_KEYS:
                    metadata[inner_meta.group(1).lower()] = inner_meta.group(2).strip()
                else:
                    had_invalid_tag = True
                    warnings.append(f"Line {line_idx}: Malformed tag '{tag}'.")

        if not line_timestamps:
            if not had_invalid_tag:
                warnings.append(f"Line {line_idx}: No valid timestamps found.")
            continue

        for ts in line_timestamps:
            sequence_counter += 1
            event = LyricLine(
                text=lyric_text,
                timestamp=ts,
                line_number=line_idx,
            )
            indexed_events.append((ts, sequence_counter, event))

    if not indexed_events:
        raise LyricsError(f"File '{resolved_path.name}' contains no valid timestamped lyric lines.")

    indexed_events.sort(key=lambda item: (item[0], item[1]))
    sorted_lines = [item[2] for item in indexed_events]

    title = metadata.get("ti", "").strip() or resolved_path.stem

    return LyricsDocument(
        title=title,
        source_path=resolved_path,
        file_format="lrc",
        lines=sorted_lines,
        metadata=metadata,
        warnings=warnings,
    )


def load_lyrics_file(file_path: str | Path) -> LyricsDocument:
    """Validate, read, and parse a .txt or .lrc file into a LyricsDocument."""
    path = validate_lyrics_path(file_path)
    content = read_utf8_file(path)
    suffix = path.suffix.lower()
    if suffix == ".lrc":
        return parse_lrc_content(content, source_path=path)
    return parse_txt_content(content, source_path=path)
