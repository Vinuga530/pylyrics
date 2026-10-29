"""Unit tests for pylyrics.config and pylyrics.cli."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pylyrics.cli import PyLyricsApp, main  # noqa: E402
from pylyrics.config import (  # noqa: E402
    DEFAULT_LINE_PAUSE,
    DEFAULT_THEME,
    DEFAULT_TYPING_SPEED,
    AppConfig,
    load_config,
    save_config,
    validate_config,
    validate_line_pause,
    validate_theme_name,
    validate_typing_speed,
)


class TestConfigAndCLI(unittest.TestCase):
    """Tests for configuration persistence, validation, and CLI navigation."""

    def test_default_config_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / ".pylyrics.json"
            cfg = load_config(missing)
            self.assertEqual(cfg.typing_speed, DEFAULT_TYPING_SPEED)
            self.assertEqual(cfg.line_pause, DEFAULT_LINE_PAUSE)
            self.assertEqual(cfg.theme, DEFAULT_THEME)
            self.assertTrue(cfg.color_enabled)

    def test_save_and_reload_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / ".pylyrics.json"
            custom = AppConfig(
                typing_speed=0.02,
                line_pause=1.25,
                theme="sage",
                color_enabled=False,
            )
            ok, err = save_config(custom, cfg_path)
            self.assertTrue(ok)
            self.assertIsNone(err)

            loaded = load_config(cfg_path)
            self.assertEqual(loaded, custom)

    def test_malformed_json_and_invalid_values_fall_back_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / ".pylyrics.json"
            cfg_path.write_text("{not valid json", encoding="utf-8")
            self.assertEqual(load_config(cfg_path), AppConfig())

            partial = validate_config(
                {
                    "typing_speed": -5.0,
                    "line_pause": "invalid",
                    "theme": "rainbow",
                    "color_enabled": "yes",
                }
            )
            self.assertEqual(partial, AppConfig())

    def test_validation_functions_reject_out_of_range_inputs(self) -> None:
        with self.assertRaises(ValueError):
            validate_typing_speed(-0.1)
        with self.assertRaises(ValueError):
            validate_typing_speed(10.0)
        with self.assertRaises(ValueError):
            validate_line_pause(-1.0)
        with self.assertRaises(ValueError):
            validate_theme_name("neon")

    def test_cli_direct_invocation_and_interactive_menu_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            cfg_path = tmp / ".pylyrics.json"
            lyrics_dir = tmp / "lyrics"
            lyrics_dir.mkdir()
            sample = lyrics_dir / "test_song.txt"
            sample.write_text("First line\nSecond line\n", encoding="utf-8")

            # Direct CLI execution with --instant and --no-color
            out = io.StringIO()
            exit_code = main(
                argv=[str(sample), "--instant", "--no-color", "--theme", "amber"],
                config_path=cfg_path,
                output_stream=out,
            )
            self.assertEqual(exit_code, 0)
            self.assertIn("First line", out.getvalue())
            self.assertIn("— end of lyrics —", out.getvalue())

            # Interactive menu navigation:
            # 2 -> settings -> 1 (speed 0) -> 3 (theme sage) -> B (back) -> 3 (Start Lyrics) -> Enter -> 4 (Exit)
            inputs = iter(["2", "1", "0", "3", "sage", "B", "3", "", "4"])
            menu_out = io.StringIO()
            app = PyLyricsApp(
                config_path=cfg_path,
                lyrics_dir=lyrics_dir,
                input_fn=lambda _prompt: next(inputs),
                output_stream=menu_out,
            )
            rc = app.run_main_menu()
            self.assertEqual(rc, 0)
            self.assertEqual(app.config.theme, "sage")
            self.assertEqual(app.config.typing_speed, 0.0)
            self.assertIn("First line", menu_out.getvalue())


if __name__ == "__main__":
    unittest.main()
