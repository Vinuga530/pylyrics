"""Unit tests for pylyrics.parser (UTF-8 TXT, Sinhala Unicode, BOMs, and LRC timestamps)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pylyrics.parser import (  # noqa: E402
    LyricsError,
    discover_lyrics_files,
    load_lyrics_file,
    parse_lrc_content,
    parse_txt_content,
    validate_lyrics_path,
)


class TestParser(unittest.TestCase):
    """Tests for TXT and LRC file loading, validation, and parsing."""

    def test_read_utf8_txt_and_preserve_internal_blank_lines(self) -> None:
        content = "\nFirst line\n\nSecond line\nThird line\n\n"
        doc = parse_txt_content(content, source_path=Path("song.txt"))
        self.assertEqual(doc.title, "song")
        self.assertEqual(doc.file_format, "txt")
        self.assertEqual(
            [line.text for line in doc.lines],
            ["First line", "", "Second line", "Third line"],
        )
        self.assertTrue(all(line.timestamp is None for line in doc.lines))

    def test_read_sinhala_txt_file_and_utf8_bom(self) -> None:
        sinhala_lines = [
            "මෙය පළමු ගී පද පේළියයි",
            "",
            "මෙය දෙවන ගී පද පේළියයි",
            "ආදරියේ ශ්‍රී ලංකාවේ",
        ]
        raw_text = "\n".join(sinhala_lines)
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "aadariye.txt"
            # Write with explicit UTF-8 BOM (EF BB BF)
            file_path.write_bytes(b"\xef\xbb\xbf" + raw_text.encode("utf-8"))

            doc = load_lyrics_file(file_path)
            self.assertEqual(doc.title, "aadariye")
            self.assertEqual([line.text for line in doc.lines], sinhala_lines)
            # Ensure BOM character was stripped from the first line
            self.assertFalse(doc.lines[0].text.startswith("\ufeff"))

    def test_invalid_utf8_encoding_raises_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "corrupt.txt"
            bad_file.write_bytes(b"\xff\xfe\xfa\xfbinvalid")
            with self.assertRaises(LyricsError) as ctx:
                load_lyrics_file(bad_file)
            self.assertIn("not valid UTF-8", str(ctx.exception))

    def test_parse_standard_lrc_and_ignore_metadata(self) -> None:
        lrc_text = (
            "[ti:Song Title]\n"
            "[ar:Artist Name]\n"
            "[al:Album Name]\n"
            "[by:Creator]\n"
            "[00:12.34]First lyric line\n"
            "[00:16.00]Second lyric line\n"
            "[00:20.50]Third lyric line\n"
        )
        doc = parse_lrc_content(lrc_text, source_path=Path("track.lrc"))
        self.assertEqual(doc.title, "Song Title")
        self.assertEqual(doc.metadata["ar"], "Artist Name")
        self.assertEqual(doc.metadata["al"], "Album Name")
        self.assertEqual(doc.metadata["by"], "Creator")
        self.assertEqual(len(doc.lines), 3)
        self.assertAlmostEqual(doc.lines[0].timestamp or 0.0, 12.34)
        self.assertEqual(doc.lines[0].text, "First lyric line")
        self.assertAlmostEqual(doc.lines[1].timestamp or 0.0, 16.00)
        self.assertEqual(doc.lines[1].text, "Second lyric line")
        self.assertAlmostEqual(doc.lines[2].timestamp or 0.0, 20.50)
        self.assertEqual(doc.lines[2].text, "Third lyric line")

    def test_parse_centisecond_and_millisecond_lrc_timestamps(self) -> None:
        lrc_text = (
            "[01:05.25]Centisecond line\n"
            "[01:05.258]Millisecond line\n"
        )
        doc = parse_lrc_content(lrc_text)
        self.assertEqual(len(doc.lines), 2)
        self.assertAlmostEqual(doc.lines[0].timestamp or 0.0, 65.25)
        self.assertAlmostEqual(doc.lines[1].timestamp or 0.0, 65.258)

    def test_multiple_timestamps_on_single_line_and_sorting(self) -> None:
        lrc_text = (
            "[00:10.00][00:30.50]Chorus refrain\n"
            "[00:20.00]Verse two\n"
            "[00:10.00]Second simultaneous line at 10s\n"
        )
        doc = parse_lrc_content(lrc_text)
        self.assertEqual(len(doc.lines), 4)
        self.assertEqual(
            [(line.timestamp, line.text) for line in doc.lines],
            [
                (10.0, "Chorus refrain"),
                (10.0, "Second simultaneous line at 10s"),
                (20.0, "Verse two"),
                (30.5, "Chorus refrain"),
            ],
        )

    def test_lrc_empty_lyric_line_and_malformed_lines_handled_gracefully(self) -> None:
        lrc_text = (
            "Random untimestamped header\n"
            "[00:75.00]Invalid seconds >= 60\n"
            "[bad:tag:format\n"
            "[00:05.00]Valid opening\n"
            "[00:08.00]\n"
            "[00:12.00]Valid closing\n"
        )
        doc = parse_lrc_content(lrc_text)
        self.assertEqual(len(doc.lines), 3)
        self.assertEqual(doc.lines[0].text, "Valid opening")
        self.assertEqual(doc.lines[1].text, "")
        self.assertEqual(doc.lines[2].text, "Valid closing")
        self.assertGreaterEqual(len(doc.warnings), 3)

    def test_empty_files_and_unsupported_extensions_raise_lyrics_error(self) -> None:
        with self.assertRaises(LyricsError):
            parse_txt_content("   \n\n  \n")

        with self.assertRaises(LyricsError):
            parse_lrc_content("[ti:Only Metadata]\n[ar:No Timestamps]\n")

        with tempfile.TemporaryDirectory() as tmpdir:
            bad_ext = Path(tmpdir) / "song.mp3"
            bad_ext.write_text("hello", encoding="utf-8")
            with self.assertRaises(LyricsError):
                validate_lyrics_path(bad_ext)

    def test_discover_lyrics_files_and_paths_with_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sub = Path(tmpdir) / "my lyrics folder"
            sub.mkdir()
            f1 = sub / "my favorite song.txt"
            f2 = sub / "second track.lrc"
            f3 = sub / "ignored.json"
            f1.write_text("Line one", encoding="utf-8")
            f2.write_text("[00:01.00]Line two", encoding="utf-8")
            f3.write_text("{}", encoding="utf-8")

            discovered = discover_lyrics_files(sub)
            self.assertEqual(
                [p.name for p in discovered],
                ["my favorite song.txt", "second track.lrc"],
            )

            # Verify quoted path with spaces validates cleanly
            validated = validate_lyrics_path(f'"{f1}"')
            self.assertEqual(validated, f1.resolve())


if __name__ == "__main__":
    unittest.main()
