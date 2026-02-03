"""Dialog for deleting a worktree."""

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from canopy.models.repository import Worktree


class DeleteWorktreeDialog(QDialog):
    """Dialog for choosing how to delete a worktree."""

    # Deletion modes
    REMOVE_FROM_LIST = "remove_from_list"
    DELETE_DIRECTORY = "delete_directory"

    def __init__(
        self,
        worktree: Worktree,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._worktree = worktree
        self._deletion_mode = self.DELETE_DIRECTORY

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setWindowTitle("Delete Worktree")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Worktree info
        info_label = QLabel(
            f"<b>Worktree:</b> {self._worktree.branch}<br>"
            f"<b>Path:</b> {self._worktree.path}"
        )
        layout.addWidget(info_label)

        # Deletion mode selection
        mode_label = QLabel("How do you want to delete this worktree?")
        layout.addWidget(mode_label)

        self._button_group = QButtonGroup(self)

        # Option 1: Remove from list only
        self._remove_from_list_radio = QRadioButton(
            "Remove from list only (keep directory)"
        )
        self._remove_from_list_radio.setToolTip(
            "Remove the worktree reference from Git, but keep the directory on disk.\n"
            "You can manually delete the directory later if needed."
        )
        self._button_group.addButton(self._remove_from_list_radio)
        layout.addWidget(self._remove_from_list_radio)

        # Description for option 1
        remove_desc = QLabel(
            "  Git will no longer track this worktree, but the files remain."
        )
        remove_desc.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(remove_desc)

        # Option 2: Delete directory
        self._delete_directory_radio = QRadioButton(
            "Delete directory from disk"
        )
        self._delete_directory_radio.setChecked(True)
        self._delete_directory_radio.setToolTip(
            "Remove the worktree and delete the directory from disk.\n"
            "This operation cannot be undone."
        )
        self._button_group.addButton(self._delete_directory_radio)
        layout.addWidget(self._delete_directory_radio)

        # Description for option 2
        delete_desc = QLabel(
            "  The worktree directory will be permanently deleted."
        )
        delete_desc.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(delete_desc)

        # Warning
        warning_label = QLabel(
            "<span style='color: #e67e22;'>Warning:</span> "
            "Make sure you have committed or stashed any important changes."
        )
        layout.addWidget(warning_label)

        layout.addStretch()

        # Buttons
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Delete")
        layout.addWidget(self._button_box)

    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        self._remove_from_list_radio.toggled.connect(self._on_mode_changed)
        self._delete_directory_radio.toggled.connect(self._on_mode_changed)

    def _on_mode_changed(self, checked: bool) -> None:
        """Handle mode radio button change."""
        if self._remove_from_list_radio.isChecked():
            self._deletion_mode = self.REMOVE_FROM_LIST
        else:
            self._deletion_mode = self.DELETE_DIRECTORY

    def get_deletion_mode(self) -> str:
        """Get the selected deletion mode."""
        return self._deletion_mode
