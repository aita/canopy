#!/usr/bin/env python3
"""Main entry point for Canopy application."""

import argparse
import logging
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from canopy.ui import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def setup_exception_hook() -> None:
    """Set up global exception hook to handle uncaught exceptions.

    This prevents the application from crashing silently when exceptions
    occur in Qt signal handlers.
    """
    original_hook = sys.excepthook

    def exception_hook(exc_type, exc_value, exc_tb):
        """Custom exception hook that logs exceptions and shows error dialog."""
        # Log the exception
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.error(f"Uncaught exception:\n{tb_str}")

        # Show error dialog if QApplication exists
        app = QApplication.instance()
        if app:
            error_msg = f"{exc_type.__name__}: {exc_value}"
            QMessageBox.critical(
                None,
                "Error",
                f"An unexpected error occurred:\n\n{error_msg}\n\nSee logs for details.",
            )

        # Call original hook
        original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = exception_hook


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

    # Set up global exception handling before creating QApplication
    setup_exception_hook()

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
