"""Interactive CLI menus and command-line argument interface for PyLyrics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Sequence, TextIO

from pylyrics.colors import THEMES, Styler, get_theme, supports_color
from pylyrics.config import (
     MAX_LINE_PAUSE,
    MAX_TYPING_SPEED,
    MIN_LINE_PAUSE,
    MIN_TYPING_SPEED,
    AppConfig,
    load_config,
    save_config,
    validate_line_pause,
    validate_theme_name,
    validate_typing_speed,
)
from pylyrics.parser import (
    LyricsError,
    discover_lyrics_files,
    load_lyrics_file,
    validate_lyrics_path,
)
from pylyrics.renderer import clear_terminal, render_document

DEFAULT_LYRICS_DIR = Path("lyrics")


class PyLyricsApp:
    """Stateful controller for the interactive PyLyrics terminal session."""

    def __init__(
        self,
        config: AppConfig | None = None,
        config_path: Path | None = None,
        lyrics_dir: Path | None = None,
        selected_file: Path | None = None,
        input_fn: Callable[[str], str] = input,
        output_stream: TextIO | None = None,
    ) -> None:
        self.config_path = config_path
        self.config: AppConfig = config if config is not None else load_config(config_path)
        self.lyrics_dir: Path = lyrics_dir if lyrics_dir is not None else DEFAULT_LYRICS_DIR
        self.selected_file: Path | None = selected_file
        self.input_fn = input_fn
        self.stream: TextIO = output_stream if output_stream is not None else sys.stdout
        self.status_message: str | None = None
        self.status_is_error: bool = False

        # Auto-select the first discovered lyrics file if none was explicitly provided
        if self.selected_file is None:
            discovered = discover_lyrics_files(self.lyrics_dir)
            if discovered:
                self.selected_file = discovered[0]

    @property
    def styler(self) -> Styler:
        """Return a Styler configured for current theme and terminal capability."""
        effective_color = self.config.color_enabled and supports_color(self.stream)
        return Styler(theme_name=self.config.theme, color_enabled=effective_color)

    def _write(self, text: str = "") -> None:
        self.stream.write(f"{text}\n")
        self.stream.flush()

    def _prompt(self, label: str) -> str:
        self.stream.write(label)
        self.stream.flush()
        return self.input_fn("")

    def _set_status(self, message: str, is_error: bool = False) -> None:
        self.status_message = message
        self.status_is_error = is_error

    def _clear_status(self) -> None:
        self.status_message = None
        self.status_is_error = False

    def _format_selected_file(self) -> str:
        if self.selected_file is None:
            return "None selected"
        try:
            rel = self.selected_file.relative_to(Path.cwd())
            return str(rel)
        except ValueError:
            return self.selected_file.name

    def _format_speed(self) -> str:
        if self.config.typing_speed == 0.0:
            return "Instant (0.0s/character)"
        return f"{self.config.typing_speed:g} seconds/character"

    def _render_banner(self) -> None:
        s = self.styler
        self._write(s.title("╭──────────────────────────────────────────╮"))
        self._write(s.title("│                P Y L Y R I C S           │"))
        self._write(s.title("│          A Minimal Terminal Experience   │"))
        self._write(s.title("╰──────────────────────────────────────────╯"))
        self._write()

    def _render_status_bar(self) -> None:
        if not self.status_message:
            return
        s = self.styler
        styled = (
            s.error(f"  ! {self.status_message}")
            if self.status_is_error
            else s.warning(f"  • {self.status_message}")
        )
        self._write(styled)
        self._write()
        self._clear_status()

    def run_main_menu(self) -> int:
        """Run the interactive main menu loop until the user exits."""
        while True:
            clear_terminal(self.stream)
            s = self.styler
            theme_info = get_theme(self.config.theme)

            self._render_banner()
            self._write(f"  {s.heading('MAIN MENU')}")
            self._write()
            self._write(
                f"  {s.secondary('Selected File :')} {s.highlight(self._format_selected_file())}"
            )
            self._write(
                f"  {s.secondary('Theme         :')} {s.highlight(theme_info.display_name)}"
            )
            self._write(
                f"  {s.secondary('Typing Speed  :')} {s.highlight(self._format_speed())}"
            )
            self._write()
            self._write(f"  {s.highlight('[1]')} Select Lyrics File")
            self._write(f"  {s.highlight('[2]')} Typography & Appearance")
            self._write(f"  {s.highlight('[3]')} Start Lyrics")
            self._write(f"  {s.highlight('[4]')} Exit")
            self._write()
            self._render_status_bar()

            try:
                choice = self._prompt(f"  {s.secondary('Enter your choice: ')}").strip().lower()
            except (KeyboardInterrupt, EOFError):
                self._write()
                return 0

            if choice == "1":
                self._handle_file_selection_menu()
            elif choice == "2":
                self._handle_settings_menu()
            elif choice == "3":
                self._handle_start_lyrics()
            elif choice in ("4", "q", "exit", "quit"):
                return 0
            else:
                self._set_status(
                    "Invalid option. Please enter 1, 2, 3, or 4.",
                    is_error=True,
                )

    def _handle_file_selection_menu(self) -> None:
        """Display the file-selection menu and update `self.selected_file` if valid."""
        while True:
            clear_terminal(self.stream)
            s = self.styler
            discovered = discover_lyrics_files(self.lyrics_dir)

            self._render_banner()
            self._write(f"  {s.heading('SELECT LYRICS FILE')}")
            self._write()

            if discovered:
                for idx, file_path in enumerate(discovered, start=1):
                    marker = " *" if self.selected_file and file_path.resolve() == self.selected_file.resolve() else ""
                    self._write(f"  {s.highlight(f'[{idx}]')} {file_path.name}{s.secondary(marker)}")
            else:
                self._write(
                    f"  {s.secondary(f'No .txt or .lrc files found in {self.lyrics_dir}/')}"
                )

            self._write()
            self._write(f"  {s.highlight('[P]')} Enter a file path manually")
            self._write(f"  {s.highlight('[B]')} Back to main menu")
            self._write()
            self._render_status_bar()

            try:
                raw_choice = self._prompt(f"  {s.secondary('Select a file: ')}").strip()
            except (KeyboardInterrupt, EOFError):
                self._clear_status()
                return

            if not raw_choice:
                self._set_status("Please select a file number, P, or B.", is_error=True)
                continue

            upper = raw_choice.upper()
            if upper == "B":
                self._clear_status()
                return

            if upper == "P":
                self._prompt_manual_path()
                if self.status_message and not self.status_is_error:
                    return
                continue

            if raw_choice.isdigit():
                index = int(raw_choice)
                if 1 <= index <= len(discovered):
                    candidate = discovered[index - 1]
                    try:
                        validated = validate_lyrics_path(candidate)
                        self.selected_file = validated
                        self._set_status(f"Selected '{validated.name}'.", is_error=False)
                        return
                    except LyricsError as exc:
                        self._set_status(str(exc), is_error=True)
                        continue

            self._set_status(
                "Invalid selection. Enter a listed number, P for a custom path, or B to go back.",
                is_error=True,
            )

    def _prompt_manual_path(self) -> None:
        """Prompt the user to enter a custom relative or absolute file path."""
        s = self.styler
        self._write()
        try:
            entered = self._prompt(
                f"  {s.secondary('Enter path to .txt or .lrc file (or press Enter to cancel): ')}"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            self._set_status("File path entry cancelled.", is_error=False)
            return

        if not entered:
            self._set_status("File path entry cancelled.", is_error=False)
            return

        try:
            validated = validate_lyrics_path(entered)
            # Also verify the file can be read and parsed before accepting
            load_lyrics_file(validated)
            self.selected_file = validated
            self._set_status(f"Selected '{validated.name}'.", is_error=False)
        except LyricsError as exc:
            self._set_status(str(exc), is_error=True)

    def _handle_settings_menu(self) -> None:
        """Display the Typography & Appearance menu and persist updates."""
        while True:
            clear_terminal(self.stream)
            s = self.styler
            theme_info = get_theme(self.config.theme)
            colors_status = "Enabled" if self.config.color_enabled else "Disabled"

            self._render_banner()
            self._write(f"  {s.heading('TYPOGRAPHY & APPEARANCE')}")
            self._write()
            self._write(
                f"  {s.highlight('[1]')} Typing Speed      : {s.lyric(f'{self.config.typing_speed:g} s/char')}"
            )
            self._write(
                f"  {s.highlight('[2]')} Line Pause        : {s.lyric(f'{self.config.line_pause:g} s')}"
            )
            self._write(
                f"  {s.highlight('[3]')} Color Theme       : {s.lyric(theme_info.display_name)}"
            )
            self._write(
                f"  {s.highlight('[4]')} Terminal Colors   : {s.lyric(colors_status)}"
            )
            self._write()
            self._write(f"  {s.highlight('[B]')} Back to main menu")
            self._write()
            self._render_status_bar()

            try:
                choice = self._prompt(f"  {s.secondary('Select an option: ')}").strip().upper()
            except (KeyboardInterrupt, EOFError):
                self._clear_status()
                return

            if choice == "B":
                self._clear_status()
                return
            elif choice == "1":
                self._update_typing_speed()
            elif choice == "2":
                self._update_line_pause()
            elif choice == "3":
                self._update_theme()
            elif choice == "4":
                new_state = not self.config.color_enabled
                self.config = self.config.with_updates(color_enabled=new_state)
                self._persist_config(
                    f"Terminal colors {'enabled' if new_state else 'disabled'}."
                )
            else:
                self._set_status("Invalid option. Enter 1, 2, 3, 4, or B.", is_error=True)

    def _update_typing_speed(self) -> None:
        s = self.styler
        self._write()
        try:
            raw = self._prompt(
                f"  {s.secondary(f'Enter typing speed in seconds ({MIN_TYPING_SPEED}–{MAX_TYPING_SPEED}, 0 for instant): ')}"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            return

        if not raw:
            return
        try:
            val = validate_typing_speed(float(raw))
            self.config = self.config.with_updates(typing_speed=val)
            self._persist_config(f"Typing speed set to {val:g} seconds/character.")
        except ValueError:
            self._set_status(
                f"Invalid typing speed. Enter a number between {MIN_TYPING_SPEED} and {MAX_TYPING_SPEED}.",
                is_error=True,
            )

    def _update_line_pause(self) -> None:
        s = self.styler
        self._write()
        try:
            raw = self._prompt(
                f"  {s.secondary(f'Enter pause between lines in seconds ({MIN_LINE_PAUSE}–{MAX_LINE_PAUSE}): ')}"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            return

        if not raw:
            return
        try:
            val = validate_line_pause(float(raw))
            self.config = self.config.with_updates(line_pause=val)
            self._persist_config(f"Line pause set to {val:g} seconds.")
        except ValueError:
            self._set_status(
                f"Invalid line pause. Enter a number between {MIN_LINE_PAUSE} and {MAX_LINE_PAUSE}.",
                is_error=True,
            )

    def _update_theme(self) -> None:
        s = self.styler
        theme_keys = list(THEMES.keys())
        self._write()
        for idx, key in enumerate(theme_keys, start=1):
            palette = THEMES[key]
            self._write(
                f"    {s.highlight(f'[{idx}]')} {palette.display_name:<12} {s.secondary(palette.description)}"
            )
        self._write()
        try:
            raw = self._prompt(
                f"  {s.secondary('Choose a theme number or name (or Enter to cancel): ')}"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            return

        if not raw:
            return

        chosen_key = raw.lower()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(theme_keys):
                chosen_key = theme_keys[idx - 1]

        try:
            valid_key = validate_theme_name(chosen_key)
            self.config = self.config.with_updates(theme=valid_key)
            display = get_theme(valid_key).display_name
            self._persist_config(f"Theme updated to {display}.")
        except ValueError as exc:
            self._set_status(str(exc), is_error=True)

    def _persist_config(self, success_msg: str) -> None:
        ok, warn = save_config(self.config, self.config_path)
        if ok:
            self._set_status(success_msg, is_error=False)
        else:
            self._set_status(f"{success_msg} ({warn})", is_error=False)

    def _handle_start_lyrics(self) -> None:
        """Validate the selected file, clear the screen, render lyrics, and return to menu."""
        if self.selected_file is None:
            self._set_status(
                "No lyrics file selected. Choose [1] Select Lyrics File first.",
                is_error=True,
            )
            return

        try:
            document = load_lyrics_file(self.selected_file)
        except LyricsError as exc:
            self._set_status(str(exc), is_error=True)
            return

        s = self.styler
        render_document(
            document=document,
            styler=s,
            char_delay=self.config.typing_speed,
            line_pause=self.config.line_pause,
            stream=self.stream,
            clear_screen=True,
            show_footer=True,
        )

        try:
            self._prompt(f"  {s.secondary('Press Enter to return to the menu.')}")
        except (KeyboardInterrupt, EOFError):
            pass


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser for PyLyrics."""
    parser = argparse.ArgumentParser(
        prog="python -m pylyrics",
        description="PyLyrics — A Minimal, Aesthetic Python CLI Lyrics Printer.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Optional path to a .txt or .lrc file to display directly.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=None,
        metavar="SECONDS",
        help=f"Character typing delay in seconds ({MIN_TYPING_SPEED}–{MAX_TYPING_SPEED}).",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=None,
        metavar="SECONDS",
        help=f"Pause between lines in seconds for TXT files ({MIN_LINE_PAUSE}–{MAX_LINE_PAUSE}).",
    )
    parser.add_argument(
        "--theme",
        type=str,
        default=None,
        choices=sorted(THEMES.keys()),
        help="Color theme override (lavender, sage, amber, monochrome).",
    )
    parser.add_argument(
        "--instant",
        action="store_true",
        help="Disable character-by-character delay (equivalent to --speed 0).",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI terminal colors.",
    )
    parser.add_argument(
        "--lyrics-dir",
        type=Path,
        default=DEFAULT_LYRICS_DIR,
        help="Directory to scan for .txt and .lrc files (default: lyrics/).",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    config_path: Path | None = None,
    output_stream: TextIO | None = None,
    input_fn: Callable[[str], str] = input,
) -> int:
    """Main entry point for `python -m pylyrics`."""
    stream = output_stream if output_stream is not None else sys.stdout
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    config = load_config(config_path)

    # Apply CLI overrides
    try:
        if args.speed is not None:
            config = config.with_updates(typing_speed=validate_typing_speed(args.speed))
        if args.instant:
            config = config.with_updates(typing_speed=0.0)
        if args.pause is not None:
            config = config.with_updates(line_pause=validate_line_pause(args.pause))
        if args.theme is not None:
            config = config.with_updates(theme=validate_theme_name(args.theme))
        if args.no_color:
            config = config.with_updates(color_enabled=False)
    except ValueError as exc:
        styler = Styler(
            theme_name=config.theme,
            color_enabled=config.color_enabled and supports_color(stream),
        )
        stream.write(f"{styler.error(f'Error: {exc}')}\n")
        stream.flush()
        return 2

    # Direct file playback mode when a file argument is given
    if args.file:
        effective_color = config.color_enabled and supports_color(stream)
        styler = Styler(theme_name=config.theme, color_enabled=effective_color)
        try:
            document = load_lyrics_file(args.file)
        except LyricsError as exc:
            stream.write(f"{styler.error(f'Error: {exc}')}\n")
            stream.flush()
            return 1

        render_document(
            document=document,
            styler=styler,
            char_delay=config.typing_speed,
            line_pause=config.line_pause,
            stream=stream,
            clear_screen=True,
            show_footer=True,
        )
        return 0

    # Interactive menu mode
    app = PyLyricsApp(
        config=config,
        config_path=config_path,
        lyrics_dir=args.lyrics_dir,
        input_fn=input_fn,
        output_stream=stream,
    )
    return app.run_main_menu()
