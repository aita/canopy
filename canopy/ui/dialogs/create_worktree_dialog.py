"""Dialog for creating a new worktree."""

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from canopy.core.git_service import GitService
from canopy.models.repository import Repository


class CreateWorktreeDialog(QDialog):
    """Dialog for creating a new worktree."""

    def __init__(
        self,
        repository: Repository,
        git_service: GitService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._git_service = git_service

        self._setup_ui()
        self._connect_signals()
        self._load_branches()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setWindowTitle("Create Worktree")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Repository info
        repo_label = QLabel(f"Repository: <b>{self._repository.name}</b>")
        layout.addWidget(repo_label)

        # Branch selection group
        branch_group = QGroupBox("Branch")
        branch_layout = QVBoxLayout(branch_group)

        # Existing branch option
        self._existing_radio = QRadioButton("Use existing branch")
        self._existing_radio.setChecked(True)
        branch_layout.addWidget(self._existing_radio)

        existing_layout = QHBoxLayout()
        existing_layout.setContentsMargins(20, 0, 0, 0)

        self._branch_combo = QComboBox()
        self._branch_combo.setMinimumWidth(250)
        existing_layout.addWidget(self._branch_combo)
        existing_layout.addStretch()

        branch_layout.addLayout(existing_layout)

        # New branch option
        self._new_radio = QRadioButton("Create new branch")
        branch_layout.addWidget(self._new_radio)

        new_branch_layout = QFormLayout()
        new_branch_layout.setContentsMargins(20, 0, 0, 0)

        self._new_branch_edit = QLineEdit()
        self._new_branch_edit.setPlaceholderText("feature/my-feature")
        self._new_branch_edit.setEnabled(False)
        new_branch_layout.addRow("Branch name:", self._new_branch_edit)

        self._base_branch_combo = QComboBox()
        self._base_branch_combo.setEnabled(False)
        new_branch_layout.addRow("Base branch:", self._base_branch_combo)

        branch_layout.addLayout(new_branch_layout)

        layout.addWidget(branch_group)

        # Worktree path
        path_group = QGroupBox("Worktree Location")
        path_layout = QVBoxLayout(path_group)

        self._auto_path_check = QCheckBox("Use automatic path")
        self._auto_path_check.setChecked(True)
        path_layout.addWidget(self._auto_path_check)

        self._auto_path_label = QLabel()
        self._auto_path_label.setStyleSheet("color: gray; margin-left: 20px;")
        path_layout.addWidget(self._auto_path_label)

        manual_layout = QHBoxLayout()
        manual_layout.setContentsMargins(20, 0, 0, 0)

        self._path_edit = QLineEdit()
        self._path_edit.setEnabled(False)
        manual_layout.addWidget(self._path_edit)

        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.setEnabled(False)
        manual_layout.addWidget(self._browse_btn)

        path_layout.addLayout(manual_layout)

        layout.addWidget(path_group)

        # Status
        self._status_label = QLabel()
        layout.addWidget(self._status_label)

        # Buttons
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self._button_box)

        self._update_auto_path()

    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        self._existing_radio.toggled.connect(self._on_branch_mode_changed)
        self._new_radio.toggled.connect(self._on_branch_mode_changed)
        self._branch_combo.currentTextChanged.connect(self._update_auto_path)
        self._new_branch_edit.textChanged.connect(self._update_auto_path)
        self._auto_path_check.toggled.connect(self._on_auto_path_changed)
        self._browse_btn.clicked.connect(self._on_browse)
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

    def _load_branches(self) -> None:
        """Load branches from the repository."""
        try:
            local_branches, remote_branches = self._git_service.list_branches(
                self._repository.path
            )

            # Get branches already in use by worktrees
            used_branches = {wt.branch for wt in self._repository.worktrees}

            # Filter out used branches for existing branch combo
            available_branches = [b for b in local_branches if b not in used_branches]

            self._branch_combo.clear()
            self._branch_combo.addItems(available_branches)

            # Add remote branches (without origin/ prefix for display)
            for rb in remote_branches:
                local_name = rb.split("/", 1)[-1] if "/" in rb else rb
                if local_name not in used_branches and local_name not in available_branches:
                    self._branch_combo.addItem(f"{local_name} (from {rb})")

            # Base branch combo - all local branches
            self._base_branch_combo.clear()
            self._base_branch_combo.addItems(local_branches)

            # Default to main/master if available
            for default in ["main", "master"]:
                if default in local_branches:
                    self._base_branch_combo.setCurrentText(default)
                    break

        except Exception as e:
            self._status_label.setText(f"Error loading branches: {e}")
            self._status_label.setStyleSheet("color: red;")

    def _on_branch_mode_changed(self, checked: bool) -> None:
        """Handle branch mode radio button change."""
        is_new = self._new_radio.isChecked()

        self._branch_combo.setEnabled(not is_new)
        self._new_branch_edit.setEnabled(is_new)
        self._base_branch_combo.setEnabled(is_new)

        self._update_auto_path()

    def _on_auto_path_changed(self, checked: bool) -> None:
        """Handle auto path checkbox change."""
        self._path_edit.setEnabled(not checked)
        self._browse_btn.setEnabled(not checked)
        self._auto_path_label.setVisible(checked)

    def _on_browse(self) -> None:
        """Handle browse button click."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Worktree Location",
            str(self._repository.path.parent),
            QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            self._path_edit.setText(path)

    def _update_auto_path(self) -> None:
        """Update the automatic path display."""
        branch = self._get_branch_name()
        if branch:
            path = self._git_service.get_default_worktree_path(
                self._repository.path, branch
            )
            self._auto_path_label.setText(str(path))
        else:
            self._auto_path_label.setText("")

    def _get_branch_name(self) -> str:
        """Get the selected or entered branch name."""
        if self._new_radio.isChecked():
            return self._new_branch_edit.text().strip()
        else:
            text = self._branch_combo.currentText()
            # Remove "(from origin/...)" suffix if present
            if " (from " in text:
                text = text.split(" (from ")[0]
            return text

    def _get_worktree_path(self) -> Path:
        """Get the worktree path."""
        if self._auto_path_check.isChecked():
            branch = self._get_branch_name()
            return self._git_service.get_default_worktree_path(
                self._repository.path, branch
            )
        else:
            return Path(self._path_edit.text())

    def _on_accept(self) -> None:
        """Handle dialog acceptance."""
        branch = self._get_branch_name()
        if not branch:
            QMessageBox.warning(
                self,
                "Invalid Branch",
                "Please enter or select a branch name.",
            )
            return

        path = self._get_worktree_path()
        if path.exists():
            QMessageBox.warning(
                self,
                "Path Exists",
                f"The path {path} already exists. Please choose a different location.",
            )
            return

        self.accept()

    def get_worktree_config(self) -> dict:
        """Get the worktree configuration."""
        return {
            "branch": self._get_branch_name(),
            "path": self._get_worktree_path(),
            "create_branch": self._new_radio.isChecked(),
            "base_branch": (
                self._base_branch_combo.currentText()
                if self._new_radio.isChecked()
                else None
            ),
        }
