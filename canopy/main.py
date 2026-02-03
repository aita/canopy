#!/usr/bin/env python3
"""Main entry point for Canopy application."""

import argparse
import sys
from pathlib import Path

import logbook
from logbook import StreamHandler
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from canopy.ui import MainWindow


def load_stylesheet() -> str:
    """Load the application stylesheet."""
    style_path = Path(__file__).parent / "resources" / "styles.qss"
    if style_path.exists():
        return style_path.read_text()
    return ""


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="canopy-gui",
        description="Claude Code Worktree IDE",
    )
    parser.add_argument(
        "repository",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Path to a Git repository (defaults to current directory)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def setup_logging(debug: bool = False) -> None:
    """Setup logging with logbook."""
    level = logbook.DEBUG if debug else logbook.INFO
    handler = StreamHandler(sys.stderr, level=level)
    handler.format_string = "[{record.time:%Y-%m-%d %H:%M:%S}] {record.level_name}: {record.channel}: {record.message}"
    handler.push_application()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_logging(debug=args.debug)

    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Canopy")
    app.setOrganizationName("Canopy")
    app.setOrganizationDomain("canopy.local")

    # Stylesheet disabled - use system default
    # stylesheet = load_stylesheet()
    # if stylesheet:
    #     app.setStyleSheet(stylesheet)

    # Create and show main window with the repository path
    window = MainWindow(repo_path=args.repository)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
