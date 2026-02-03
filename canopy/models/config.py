"""Application configuration management."""

import json
from dataclasses import dataclass, field
from pathlib import Path


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    config_dir = Path.home() / ".config" / "canopy"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get the main configuration file path."""
    return get_config_dir() / "config.json"


def get_repos_file() -> Path:
    """Get the repositories file path."""
    return get_config_dir() / "repos.json"


def get_sessions_dir() -> Path:
    """Get the sessions directory path."""
    sessions_dir = get_config_dir() / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


@dataclass
class AppConfig:
    """Application configuration."""

    # Repository paths
    repositories: list[str] = field(default_factory=list)

    # Window geometry
    window_width: int = 1200
    window_height: int = 800
    window_x: int | None = None
    window_y: int | None = None
    splitter_sizes: list[int] = field(default_factory=lambda: [250, 950])

    # Claude Code settings
    claude_command: str = "claude"
    default_output_format: str = "json"

    # UI settings
    theme: str = "system"
    font_size: int = 12

    def save(self) -> None:
        """Save configuration to file."""
        config_file = get_config_file()
        with open(config_file, "w") as f:
            json.dump(self._to_dict(), f, indent=2)

    def _to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "repositories": self.repositories,
            "window": {
                "width": self.window_width,
                "height": self.window_height,
                "x": self.window_x,
                "y": self.window_y,
                "splitter_sizes": self.splitter_sizes,
            },
            "claude": {
                "command": self.claude_command,
                "default_output_format": self.default_output_format,
            },
            "ui": {
                "theme": self.theme,
                "font_size": self.font_size,
            },
        }

    @classmethod
    def load(cls) -> "AppConfig":
        """Load configuration from file."""
        config_file = get_config_file()
        if not config_file.exists():
            return cls()

        try:
            with open(config_file) as f:
                data = json.load(f)
            return cls._from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return cls()

    @classmethod
    def _from_dict(cls, data: dict) -> "AppConfig":
        """Create from dictionary."""
        window = data.get("window", {})
        claude = data.get("claude", {})
        ui = data.get("ui", {})

        return cls(
            repositories=data.get("repositories", []),
            window_width=window.get("width", 1200),
            window_height=window.get("height", 800),
            window_x=window.get("x"),
            window_y=window.get("y"),
            splitter_sizes=window.get("splitter_sizes", [250, 950]),
            claude_command=claude.get("command", "claude"),
            default_output_format=claude.get("default_output_format", "json"),
            theme=ui.get("theme", "system"),
            font_size=ui.get("font_size", 12),
        )

    def add_repository(self, path: str) -> None:
        """Add a repository path."""
        if path not in self.repositories:
            self.repositories.append(path)
            self.save()

    def remove_repository(self, path: str) -> None:
        """Remove a repository path."""
        if path in self.repositories:
            self.repositories.remove(path)
            self.save()
