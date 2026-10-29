"""Unit tests for pylyrics.renderer and pylyrics.colors."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pylyrics.colors import RESET, Styler  # noqa: E402
from pylyrics.parser import LyricLine, LyricsDocument  # noqa: E402
from pylyrics.renderer import (  # noqa: E402
    render_document,
    render_line_animated,
    segment_graphemes,
)


class FakeClock:
    """Deterministic fake monotonic clock and sleep recorder for fast testing."""

    def __init__(self, initial: float = 0.0) -> None:
        self.now = initial
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class TestRenderer(unittest.TestCase):
    """Tests for Unicode grapheme segmentation, typewriter rendering, and LRC timing."""

    def test_sinhala_grapheme_segmentation_preserves_combining_marks(self) -> None:
        # "ආදරියේ" -> ["ආ", "ද", "රි", "යේ"]
        word = "ආදරියේ"
        clusters = segment_graphemes(word)
        self.assertEqual(clusters, ["ආ", "ද", "රි", "යේ"])
        self.assertEqual("".join(clusters), word)

    def test_sinhala_conjuncts_with_virama_and_zwj_stay_grouped(self) -> None:
        # "ශ්‍රී" uses ශ + ් (U+0DCA) + ZWJ (U+200D) + ර + ී (U+0DD3)
        shri = "ශ\u0dca\u200dරී"
        clusters = segment_graphemes(shri)
        self.assertEqual(clusters, [shri])

        # Mixed Sinhala phrase
        phrase = "ශ්‍රී ලංකාව"
        phrase_clusters = segment_graphemes(phrase)
        self.assertEqual(phrase_clusters, ["ශ\u0dca\u200dරී", " ", "ලං", "කා", "ව"])

    def test_render_line_animated_writes_progressively_on_same_line(self) -> None:
        buf = io.StringIO()
        clock = FakeClock()
        styler = Styler(theme_name="lavender", color_enabled=False)

        render_line_animated(
            text="ආදරියේ",
            styler=styler,
            char_delay=0.05,
            indent="  ",
            stream=buf,
            sleep_fn=clock.sleep,
        )

        output = buf.getvalue()
        # Only one newline at the very end of the line
        self.assertEqual(output, "  ආදරියේ\n")
        self.assertEqual(len(clock.sleeps), 4)
        self.assertTrue(all(abs(s - 0.05) < 1e-9 for s in clock.sleeps))

    def test_instant_mode_introduces_no_character_delays(self) -> None:
        buf = io.StringIO()
        clock = FakeClock()
        styler = Styler(theme_name="sage", color_enabled=False)

        doc = LyricsDocument(
            title="Instant Track",
            source_path=Path("instant.txt"),
            file_format="txt",
            lines=[
                LyricLine(text="First line"),
                LyricLine(text="Second line"),
            ],
        )

        completed = render_document(
            document=doc,
            styler=styler,
            char_delay=0.0,
            line_pause=0.0,
            stream=buf,
            sleep_fn=clock.sleep,
            clock_fn=clock,
            clear_screen=False,
        )
        self.assertTrue(completed)
        self.assertEqual(clock.sleeps, [])
        self.assertIn("First line", buf.getvalue())
        self.assertIn("Second line", buf.getvalue())

    def test_colors_disabled_emits_no_ansi_color_codes(self) -> None:
        buf = io.StringIO()
        clock = FakeClock()
        styler = Styler(theme_name="amber", color_enabled=False)

        render_line_animated(
            text="Plain text line",
            styler=styler,
            char_delay=0.02,
            stream=buf,
            sleep_fn=clock.sleep,
        )
        self.assertNotIn("\033[38;2;", buf.getvalue())
        self.assertNotIn(RESET, buf.getvalue())

    def test_colors_enabled_wraps_line_once_without_breaking_characters(self) -> None:
        buf = io.StringIO()
        clock = FakeClock()
        styler = Styler(theme_name="lavender", color_enabled=True)

        render_line_animated(
            text="Hi",
            styler=styler,
            char_delay=0.02,
            indent="",
            stream=buf,
            sleep_fn=clock.sleep,
        )
        out = buf.getvalue()
        self.assertTrue(out.startswith(styler.palette.lyrics + "Hi" + RESET + "\n"))
        self.assertEqual(out.count("\033[38;2;"), 1)

    def test_lrc_timestamp_scheduling_and_overlap_handling(self) -> None:
        buf = io.StringIO()
        clock = FakeClock()
        styler = Styler(theme_name="monochrome", color_enabled=False)

        doc = LyricsDocument(
            title="Timed Song",
            source_path=Path("timed.lrc"),
            file_format="lrc",
            lines=[
                LyricLine(text="Hello", timestamp=1.0),
                LyricLine(text="Yo", timestamp=2.0),
                LyricLine(text="End", timestamp=6.0),
            ],
        )

        completed = render_document(
            document=doc,
            styler=styler,
            char_delay=0.5,
            stream=buf,
            sleep_fn=clock.sleep,
            clock_fn=clock,
            clear_screen=False,
        )
        self.assertTrue(completed)
        rendered = buf.getvalue()
        self.assertIn("Hello", rendered)
        self.assertIn("Yo", rendered)
        self.assertIn("End", rendered)
        self.assertAlmostEqual(clock.now, 7.5)


if __name__ == "__main__":
    unittest.main()
