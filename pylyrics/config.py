"""Configuration management for PyLyrics (~/.pylyrics.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pylyrics.colors import DEFAULT_THEME, THEMES

DEFAULT_TYPING_SPEED = 0.045
DEFAULT_LINE_PAUSE = 0.75
DEFAULT_COLOR_ENABLED = True
DEFAULT_CONFIG_PATH = Path.home() / ".pylyrics.json"

MIN_TYPING_SPEED = 0.0
MAX_TYPING_SPEED = 2.0

MIN_LINE_PAUSE = 0.0
MAX_LINE_PAUSE = 30.0


@dataclass(frozen=True)
class AppConfig:
    """Validated user preferences for PyLyrics."""

    typing_speed: float = DEFAULT_TYPING_SPEED
    line_pause: float = DEFAULT_LINE_PAUSE
    theme: str = DEFAULT_THEME
    color_enabled: bool = DEFAULT_COLOR_ENABLED

    def with_updates(self, **kwargs: Any) -> AppConfig:
        """Return a new validated AppConfig with the specified fields updated."""
        candidate = replace(self, **kwargs)
        return validate_config(
            {
                "typing_speed": candidate.typing_speed,
                "line_pause": candidate.line_pause,
                "theme": candidate.theme,
                "color_enabled": candidate.color_enabled,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration to a JSON-compatible dictionary."""
        return {
            "typing_speed": round(float(self.typing_speed), 4),
            "line_pause": round(float(self.line_pause), 4),
            "theme": self.theme,
            "color_enabled": bool(self.color_enabled),
        }


def validate_typing_speed(value: Any) -> float:
    """Validate and return a typing speed in seconds per character."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Typing speed must be a number.")
    speed = float(value)
    if speed != speed or speed < MIN_TYPING_SPEED or speed > MAX_TYPING_SPEED:
        raise ValueError(
            f"Typing speed must be between {MIN_TYPING_SPEED} and {MAX_TYPING_SPEED} seconds."
        )
    return speed


def validate_line_pause(value: Any) -> float:
    """Validate and return a line pause in seconds."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Line pause must be a number.")
    pause = float(value)
    if pause != pause or pause < MIN_LINE_PAUSE or pause > MAX_LINE_PAUSE:
        raise ValueError(
            f"Line pause must be between {MIN_LINE_PAUSE} and {MAX_LINE_PAUSE} seconds."
        )
    return pause


def validate_theme_name(value: Any) -> str:
    """Validate and return a supported theme key."""
    if not isinstance(value, str):
        raise ValueError("Theme name must be a string.")
    normalized = value.strip().lower()
    if normalized not in THEMES:
        valid = ", ".join(sorted(THEMES.keys()))
        raise ValueError(f"Unsupported theme '{value}'. Choose from: {valid}.")
    return normalized


def validate_color_enabled(value: Any) -> bool:
    """Validate and return a boolean color setting."""
    if not isinstance(value, bool):
        raise ValueError("color_enabled must be a boolean.")
    return value


def validate_config(raw: dict[str, Any]) -> AppConfig:
    """Construct an AppConfig from raw dictionary values, falling back per-field if invalid."""
    if not isinstance(raw, dict):
        return AppConfig()

    try:
        typing_speed = validate_typing_speed(raw.get("typing_speed", DEFAULT_TYPING_SPEED))
    except ValueError:
        typing_speed = DEFAULT_TYPING_SPEED

    try:
        line_pause = validate_line_pause(raw.get("line_pause", DEFAULT_LINE_PAUSE))
    except ValueError:
        line_pause = DEFAULT_LINE_PAUSE

    try:
        theme = validate_theme_name(raw.get("theme", DEFAULT_THEME))
    except ValueError:
        theme = DEFAULT_THEME

    try:
        color_enabled = validate_color_enabled(raw.get("color_enabled", DEFAULT_COLOR_ENABLED))
    except ValueError:
        color_enabled = DEFAULT_COLOR_ENABLED

    return AppConfig(
        typing_speed=typing_speed,
        line_pause=line_pause,
        theme=theme,
        color_enabled=color_enabled,
    )


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from ~/.pylyrics.json, returning safe defaults on any error."""
    target = config_path if config_path is not None else DEFAULT_CONFIG_PATH
    try:
        if not target.exists() or not target.is_file():
            return AppConfig()
        content = target.read_text(encoding="utf-8-sig")
        data = json.loads(content)
        if not isinstance(data, dict):
            return AppConfig()
        return validate_config(data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return AppConfig()


def save_config(config: AppConfig, config_path: Path | None = None) -> tuple[bool, str | None]:
    """Save configuration safely to ~/.pylyrics.json.

    Returns (True, None) on success, or (False, warning_message) if saving fails.
    """
    target = config_path if config_path is not None else DEFAULT_CONFIG_PATH
    try:
        if target.exists() and target.is_dir():
            return False, f"Cannot save settings: '{target}' is a directory."
        payload = json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n"
        temp_path = target.with_name(f"{target.name}.tmp")
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(target)
        return True, None
    except OSError as exc:
        return False, f"Could not save settings to {target}: {exc}"
