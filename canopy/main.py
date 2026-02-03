#!/usr/bin/env python3
"""Main entry point for Canopy application."""

import argparse
import sys
from pathlib import Path

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
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

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
