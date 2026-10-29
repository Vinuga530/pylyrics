# PyLyrics — A Minimal, Aesthetic Python CLI Lyrics Printer

PyLyrics is a self-contained command-line utility for displaying song lyrics inside the terminal with progressive letter-by-letter typography, restrained true-color themes, UTF-8/Sinhala Unicode support, and timestamped `.lrc` scheduling.

It operates entirely inside the terminal using only the Python standard library—no GUI, no web server, no audio playback, and no external runtime dependencies.

## Requirements

- **Python**: 3.10 or newer
- **Dependencies**: None (100% Python standard library)
- **Terminal**: Windows Terminal, Windows PowerShell, macOS Terminal / iTerm2, or any Linux terminal supporting UTF-8 and ANSI escape sequences (with automatic fallback when colors are disabled or unsupported).

## Project Structure

```text
pylyrics/
├── pylyrics/
│   ├── __init__.py      # Package version metadata
│   ├── __main__.py      # Entry point for `python -m pylyrics`
│   ├── cli.py           # Interactive menus and CLI argument parser
│   ├── parser.py        # UTF-8 TXT and LRC parsing & validation
│   ├── renderer.py      # Unicode grapheme segmentation & typewriter rendering
│   ├── colors.py        # Restrained true-color palettes & ANSI styling
│   └── config.py        # Persistent JSON settings (`~/.pylyrics.json`)
├── lyrics/
│   ├── example.txt      # Original UTF-8 Sinhala & English plain-text sample
│   └── example.lrc      # Original timestamped LRC sample
├── tests/
│   ├── test_parser.py   # Unit tests for TXT, LRC, BOM, and Sinhala loading
│   ├── test_renderer.py # Unit tests for grapheme segmentation & timing
│   └── test_config.py   # Unit tests for settings persistence & CLI flow
├── pyproject.toml
├── README.md
├── .gitignore
└── LICENSE
```

## How to Run

### 1. Interactive Menu Mode

Launch the interactive main menu from the project root:

```bash
python -m pylyrics
```

From the main menu you can:
- **`[1] Select Lyrics File`**: Pick a discovered `.txt` or `.lrc` file from `lyrics/`, or press `P` to enter any custom relative or absolute file path (supports spaces and `~` expansion).
- **`[2] Typography & Appearance`**: Adjust character typing speed (`0` for instant mode), line pause duration, color theme (`Lavender`, `Sage`, `Amber`, `Monochrome`), or toggle ANSI colors on/off.
- **`[3] Start Lyrics`**: Clear the terminal and begin the immersive lyrics display. Press `Ctrl+C` at any time during playback to interrupt cleanly and return to the menu.
- **`[4] Exit`**: Quit the application.

### 2. Direct Command-Line Mode

You can also open and render a `.txt` or `.lrc` file directly from the command line:

```bash
# Display a plain-text lyrics file
python -m pylyrics lyrics/example.txt

# Display a timestamped LRC file
python -m pylyrics lyrics/example.lrc

# Override character typing delay (in seconds)
python -m pylyrics lyrics/example.txt --speed 0.025

# Override the color theme (lavender, sage, amber, monochrome)
python -m pylyrics lyrics/example.txt --theme sage

# Disable character-by-character delay
python -m pylyrics lyrics/example.txt --instant

# Disable ANSI colors
python -m pylyrics lyrics/example.txt --no-color
```

## Formatting Lyrics Files

### UTF-8 `.txt` Files

- Save files with **UTF-8** encoding (both standard UTF-8 and UTF-8 with BOM are supported).
- Place one lyric line per line.
- **Blank-line policy**: Leading and trailing blank lines at the start/end of the file are trimmed automatically; internal blank lines between stanzas are preserved as visual stanza breaks.

### Timestamped `.lrc` Files

- Standard LRC timestamps in `[MM:SS.xx]` (centiseconds) or `[MM:SS.xxx]` (milliseconds) are supported:
  ```text
  [ti:Midnight Monsoon]
  [ar:PyLyrics Studio]
  [00:00.50]සැඳෑ අහසේ තරු පායනා වෙලාවේ
  [00:02.20]Soft rain gathers on the windowpane
  [00:05.80]
  [00:06.50][00:09.25]Echoes fading into calm silence
  ```
- **Metadata tags**: Tags such as `[ti:]`, `[ar:]`, `[al:]`, and `[by:]` are ignored as lyric events; `[ti:]` and `[ar:]` are used to display the header if present.
- **Multiple timestamps per line**: Lines like `[00:06.50][00:09.25]Chorus` expand into separate events at each timestamp and are sorted chronologically (preserving relative order for simultaneous timestamps).
- **Empty timestamped lines**: A line with a timestamp and empty text (e.g., `[00:05.80]`) renders an empty stanza break at that timestamp.
- **Timing & overlap policy**: PyLyrics is a text-only terminal application and does not play audio. Each line is scheduled against a monotonic clock (`session_start + timestamp`). If a long line or slow typing speed causes a line's animation to finish after the next line's timestamp has already passed, the next line begins immediately without skipping lyrics or truncating characters, while subsequent lines remain anchored to `session_start` to prevent cumulative timing drift.

## Themes & Persistent Configuration

PyLyrics includes four restrained true-color palettes that respect your terminal's native background color:

| Theme | Accent | Lyrics | Secondary | Highlight |
| :--- | :--- | :--- | :--- | :--- |
| **Lavender** *(default)* | `#B7A4D4` | `#EEEAF3` | `#8D929B` | `#D6B58B` |
| **Sage** | `#9AB8A2` | `#EFF2EE` | `#8C948E` | `#C8B88A` |
| **Amber** | `#D4A359` | `#F5EFE6` | `#948E86` | `#E0B97D` |
| **Monochrome** | `#D4D4D4` | `#F2F2F2` | `#8A8A8A` | `#BDBDBD` |

User preferences (`typing_speed`, `line_pause`, `theme`, `color_enabled`) are automatically loaded from and saved to `~/.pylyrics.json`. If the file is missing or malformed, PyLyrics safely falls back to defaults.

## Sinhala Unicode & Terminal Shaping Notes

- **Grapheme-cluster segmentation**: `pylyrics/renderer.py` implements Unicode grapheme segmentation using Python's standard-library `unicodedata` module. It groups base characters with all trailing combining marks (`Mn`, `Mc`, `Me`, such as Sinhala vowel signs `ා`, `ැ`, `ි`, `ී`, `ු`, `ූ`, `ෙ`, `ේ`, `ො`, `ෝ`, and al-lakuna `්`) as well as Zero Width Joiner (`U+200D`) conjunct sequences (such as Yansaya `්\u200dය` and Rakaransaya `්\u200dර`). This avoids splitting Sinhala syllables mid-animation without requiring external C/Rust grapheme libraries.
- **Terminal & font requirements**: While PyLyrics emits complete Unicode grapheme clusters in UTF-8, final visual shaping of complex Sinhala ligatures depends on your terminal emulator's HarfBuzz/DirectWrite text shaping support and having a Sinhala-capable font installed (such as *Noto Sans Sinhala*, *Iskoola Pota*, or *Nirmala UI*).

## Running the Automated Test Suite

Run the full unit test suite from the project root using Python's built-in `unittest` runner:

```bash
python -m unittest discover -s tests -v
```
