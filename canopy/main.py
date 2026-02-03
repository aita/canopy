#!/usr/bin/env python3
"""Main entry point for Canopy application."""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from canopy.ui import MainWindow


def load_stylesheet() -> str:
    """Load the application stylesheet."""
    style_path = Path(__file__).parent / "resources" / "styles.qss"
    if style_path.exists():
        return style_path.read_text()
    return ""


def main() -> int:
    """Main entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Canopy")
    app.setOrganizationName("Canopy")
    app.setOrganizationDomain("canopy.local")

    # Load stylesheet
    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    # Create and show main window
    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
