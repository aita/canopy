"""Dialog for adding a Git repository."""

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from canopy.core.git_service import GitService


class AddRepoDialog(QDialog):
    """Dialog for adding a Git repository."""

    def __init__(
        self,
        git_service: GitService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._git_service = git_service
        self._selected_path: Optional[Path] = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setWindowTitle("Add Repository")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Instructions
        instructions = QLabel(
            "Select a Git repository to add. The repository must already exist "
            "and be initialized with Git."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Path selection
        path_layout = QHBoxLayout()

        path_label = QLabel("Repository Path:")
        path_layout.addWidget(path_label)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("/path/to/repository")
        path_layout.addWidget(self._path_edit)

        self._browse_btn = QPushButton("Browse...")
        path_layout.addWidget(self._browse_btn)

        layout.addLayout(path_layout)

        # Status label
        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: gray;")
        layout.addWidget(self._status_label)

        # Buttons
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self._button_box)

    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        self._browse_btn.clicked.connect(self._on_browse)
        self._path_edit.textChanged.connect(self._on_path_changed)
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

    def _on_browse(self) -> None:
        """Handle browse button click."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Git Repository",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            self._path_edit.setText(path)

    def _on_path_changed(self, text: str) -> None:
        """Handle path text change."""
        path = Path(text) if text else None
        ok_btn = self._button_box.button(QDialogButtonBox.StandardButton.Ok)

        if not path or not path.exists():
            self._status_label.setText("Path does not exist")
            self._status_label.setStyleSheet("color: red;")
            ok_btn.setEnabled(False)
            self._selected_path = None
            return

        if not path.is_dir():
            self._status_label.setText("Path is not a directory")
            self._status_label.setStyleSheet("color: red;")
            ok_btn.setEnabled(False)
            self._selected_path = None
            return

        if not self._git_service.is_git_repository(path):
            self._status_label.setText("Not a Git repository")
            self._status_label.setStyleSheet("color: red;")
            ok_btn.setEnabled(False)
            self._selected_path = None
            return

        # Valid repository
        self._selected_path = path.resolve()
        self._status_label.setText(f"✓ Valid Git repository: {path.name}")
        self._status_label.setStyleSheet("color: green;")
        ok_btn.setEnabled(True)

    def _on_accept(self) -> None:
        """Handle dialog acceptance."""
        if self._selected_path:
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "Invalid Repository",
                "Please select a valid Git repository.",
            )

    def get_repository_path(self) -> Optional[Path]:
        """Get the selected repository path."""
        return self._selected_path
