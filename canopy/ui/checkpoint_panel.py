"""Checkpoint panel for saving and restoring worktree states."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from canopy.core.git_service import GitError, GitService


class CheckpointItem(QListWidgetItem):
    """List item representing a checkpoint (git stash)."""

    def __init__(self, stash_info: dict) -> None:
        super().__init__()
        self.stash_info = stash_info
        self._setup_display()

    def _setup_display(self) -> None:
        """Set up the display."""
        ref = self.stash_info["ref"]
        branch = self.stash_info.get("branch", "")
        message = self.stash_info.get("message", "")

        # Extract index from ref (stash@{0} -> 0)
        try:
            index = ref.split("{")[1].split("}")[0]
        except IndexError:
            index = "?"

        if message:
            self.setText(f"#{index}: {message}")
        else:
            self.setText(f"#{index}: {branch}")

        self.setToolTip(f"Branch: {branch}\nRef: {ref}")


class CheckpointPanel(QWidget):
    """Panel for managing checkpoints (git stashes)."""

    checkpoint_created = Signal(str)  # stash_ref
    checkpoint_restored = Signal(str)  # stash_ref
    checkpoint_deleted = Signal(str)  # stash_ref

    def __init__(
        self,
        git_service: GitService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._git_service = git_service
        self._worktree_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("""
            background-color: #1e1e1e;
            border-bottom: 1px solid #3a3a3a;
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Checkpoints")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Create checkpoint button
        create_btn = QPushButton("+")
        create_btn.setFixedSize(24, 24)
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                border: none;
                border-radius: 3px;
                font-size: 14px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
        """)
        create_btn.setToolTip("Create checkpoint")
        create_btn.clicked.connect(self._on_create_checkpoint)
        header_layout.addWidget(create_btn)

        # Refresh button
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(24, 24)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        layout.addWidget(header)

        # Checkpoint list
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: none;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #2a2a2a;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
            QListWidget::item:hover {
                background-color: #2a2a2a;
            }
        """)
        layout.addWidget(self._list)

        # Actions bar
        actions_bar = QWidget()
        actions_bar.setStyleSheet("background-color: #252525;")
        actions_layout = QHBoxLayout(actions_bar)
        actions_layout.setContentsMargins(8, 6, 8, 6)

        # Restore button
        restore_btn = QPushButton("Restore")
        restore_btn.setStyleSheet("""
            QPushButton {
                background-color: #d97706;
                border: none;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
                color: white;
            }
            QPushButton:hover {
                background-color: #b45309;
            }
        """)
        restore_btn.clicked.connect(self._on_restore)
        actions_layout.addWidget(restore_btn)

        # Apply button (restore without dropping)
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                border: none;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
                color: white;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        apply_btn.clicked.connect(self._on_apply)
        actions_layout.addWidget(apply_btn)

        actions_layout.addStretch()

        # Delete button
        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                border: none;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
                color: white;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        delete_btn.clicked.connect(self._on_delete)
        actions_layout.addWidget(delete_btn)

        layout.addWidget(actions_bar)

    def set_worktree(self, worktree_path: Path) -> None:
        """Set the worktree to manage checkpoints for."""
        self._worktree_path = worktree_path
        self.refresh()

    def refresh(self) -> None:
        """Refresh the checkpoint list."""
        self._list.clear()

        if not self._worktree_path:
            return

        try:
            stashes = self._git_service.list_stashes(self._worktree_path)
            for stash in stashes:
                item = CheckpointItem(stash)
                self._list.addItem(item)
        except GitError as e:
            # Silently ignore errors (e.g., not a git repo)
            pass

    def _get_selected_stash(self) -> str | None:
        """Get the selected stash reference."""
        item = self._list.currentItem()
        if isinstance(item, CheckpointItem):
            return item.stash_info["ref"]
        return None

    def _on_create_checkpoint(self) -> None:
        """Handle create checkpoint button click."""
        if not self._worktree_path:
            return

        # Ask for a message
        message, ok = QInputDialog.getText(
            self,
            "Create Checkpoint",
            "Enter a description for this checkpoint:",
        )

        if not ok:
            return

        try:
            ref = self._git_service.create_stash(
                self._worktree_path,
                message=message or None,
                include_untracked=True,
            )
            self.refresh()
            self.checkpoint_created.emit(ref)
        except GitError as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to create checkpoint:\n{e}",
            )

    def _on_restore(self) -> None:
        """Handle restore button click (pop stash)."""
        ref = self._get_selected_stash()
        if not ref or not self._worktree_path:
            return

        reply = QMessageBox.question(
            self,
            "Restore Checkpoint",
            f"Restore checkpoint and remove it from the list?\n\n{ref}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._git_service.apply_stash(
                self._worktree_path,
                stash_ref=ref,
                pop=True,
            )
            self.refresh()
            self.checkpoint_restored.emit(ref)
        except GitError as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to restore checkpoint:\n{e}",
            )

    def _on_apply(self) -> None:
        """Handle apply button click (apply without dropping)."""
        ref = self._get_selected_stash()
        if not ref or not self._worktree_path:
            return

        try:
            self._git_service.apply_stash(
                self._worktree_path,
                stash_ref=ref,
                pop=False,
            )
            self.checkpoint_restored.emit(ref)
        except GitError as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to apply checkpoint:\n{e}",
            )

    def _on_delete(self) -> None:
        """Handle delete button click."""
        ref = self._get_selected_stash()
        if not ref or not self._worktree_path:
            return

        reply = QMessageBox.question(
            self,
            "Delete Checkpoint",
            f"Delete this checkpoint?\n\n{ref}\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._git_service._run_git(
                ["stash", "drop", ref],
                cwd=self._worktree_path,
            )
            self.refresh()
            self.checkpoint_deleted.emit(ref)
        except GitError as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to delete checkpoint:\n{e}",
            )
