"""Worktree panel widget for the sidebar."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from canopy.core.git_service import GitService
from canopy.models.repository import Repository, Worktree
from canopy.models.session import Session


class WorktreePanel(QWidget):
    """Left sidebar panel showing repositories, worktrees, and sessions."""

    # Signals
    worktree_selected = Signal(Worktree)
    session_selected = Signal(Session)
    add_repository_requested = Signal()
    create_worktree_requested = Signal(Repository)
    remove_worktree_requested = Signal(Repository, Worktree)
    create_session_requested = Signal(Worktree)
    remove_session_requested = Signal(Session)

    # Item types for tree widget
    REPO_TYPE = 1
    WORKTREE_TYPE = 2
    SESSION_TYPE = 3

    def __init__(
        self,
        git_service: GitService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._git_service = git_service
        self._repositories: list[Repository] = []
        self._sessions_by_worktree: dict[Path, list[Session]] = {}

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)

        # Make tree expand to fill width
        header = self._tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self._tree)

        # Button bar
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(4, 4, 4, 4)

        self._add_repo_btn = QPushButton("+ Repository")
        self._add_repo_btn.setToolTip("Add a Git repository")
        button_layout.addWidget(self._add_repo_btn)

        self._add_worktree_btn = QPushButton("+ Worktree")
        self._add_worktree_btn.setToolTip("Create a new worktree")
        self._add_worktree_btn.setEnabled(False)
        button_layout.addWidget(self._add_worktree_btn)

        layout.addLayout(button_layout)

    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._add_repo_btn.clicked.connect(self.add_repository_requested.emit)
        self._add_worktree_btn.clicked.connect(self._on_add_worktree_clicked)

    def add_repository(self, repo: Repository) -> None:
        """Add a repository to the panel."""
        if repo not in self._repositories:
            self._repositories.append(repo)
        self._refresh_tree()

    def remove_repository(self, repo: Repository) -> None:
        """Remove a repository from the panel."""
        if repo in self._repositories:
            self._repositories.remove(repo)
        self._refresh_tree()

    def update_repository(self, repo: Repository) -> None:
        """Update repository data (e.g., worktrees changed)."""
        for i, r in enumerate(self._repositories):
            if r.path == repo.path:
                self._repositories[i] = repo
                break
        self._refresh_tree()

    def set_sessions(self, worktree_path: Path, sessions: list[Session]) -> None:
        """Set sessions for a worktree."""
        self._sessions_by_worktree[worktree_path] = sessions
        self._refresh_tree()

    def get_selected_repository(self) -> Optional[Repository]:
        """Get the currently selected repository."""
        item = self._tree.currentItem()
        if not item:
            return None

        # Walk up to find repo
        while item:
            if item.type() == self.REPO_TYPE:
                return item.data(0, Qt.ItemDataRole.UserRole)
            item = item.parent()
        return None

    def get_selected_worktree(self) -> Optional[Worktree]:
        """Get the currently selected worktree."""
        item = self._tree.currentItem()
        if not item:
            return None

        if item.type() == self.WORKTREE_TYPE:
            return item.data(0, Qt.ItemDataRole.UserRole)
        elif item.type() == self.SESSION_TYPE:
            parent = item.parent()
            if parent and parent.type() == self.WORKTREE_TYPE:
                return parent.data(0, Qt.ItemDataRole.UserRole)
        return None

    def _refresh_tree(self) -> None:
        """Refresh the tree widget."""
        self._tree.clear()

        for repo in self._repositories:
            repo_item = QTreeWidgetItem(self._tree, self.REPO_TYPE)
            repo_item.setText(0, repo.name)
            repo_item.setData(0, Qt.ItemDataRole.UserRole, repo)
            repo_item.setExpanded(True)

            for worktree in repo.worktrees:
                wt_item = QTreeWidgetItem(repo_item, self.WORKTREE_TYPE)
                wt_item.setText(0, worktree.name)
                wt_item.setData(0, Qt.ItemDataRole.UserRole, worktree)
                wt_item.setToolTip(0, str(worktree.path))

                # Add sessions under worktree
                sessions = self._sessions_by_worktree.get(worktree.path, [])
                for session in sessions:
                    session_item = QTreeWidgetItem(wt_item, self.SESSION_TYPE)
                    session_item.setText(0, session.name)
                    session_item.setData(0, Qt.ItemDataRole.UserRole, session)

    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        item = self._tree.currentItem()
        if not item:
            self._add_worktree_btn.setEnabled(False)
            return

        # Enable add worktree button if a repo or worktree is selected
        self._add_worktree_btn.setEnabled(
            item.type() in (self.REPO_TYPE, self.WORKTREE_TYPE, self.SESSION_TYPE)
        )

        if item.type() == self.WORKTREE_TYPE:
            worktree = item.data(0, Qt.ItemDataRole.UserRole)
            self.worktree_selected.emit(worktree)
        elif item.type() == self.SESSION_TYPE:
            session = item.data(0, Qt.ItemDataRole.UserRole)
            self.session_selected.emit(session)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle double-click on item."""
        if item.type() == self.WORKTREE_TYPE:
            worktree = item.data(0, Qt.ItemDataRole.UserRole)
            # Create a new session for this worktree
            self.create_session_requested.emit(worktree)
        elif item.type() == self.SESSION_TYPE:
            session = item.data(0, Qt.ItemDataRole.UserRole)
            self.session_selected.emit(session)

    def _on_add_worktree_clicked(self) -> None:
        """Handle add worktree button click."""
        repo = self.get_selected_repository()
        if repo:
            self.create_worktree_requested.emit(repo)

    def _show_context_menu(self, pos) -> None:
        """Show context menu for tree items."""
        item = self._tree.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)

        if item.type() == self.REPO_TYPE:
            repo = item.data(0, Qt.ItemDataRole.UserRole)

            refresh_action = QAction("Refresh", self)
            refresh_action.triggered.connect(lambda: self._refresh_repository(repo))
            menu.addAction(refresh_action)

            add_wt_action = QAction("Add Worktree...", self)
            add_wt_action.triggered.connect(
                lambda: self.create_worktree_requested.emit(repo)
            )
            menu.addAction(add_wt_action)

            menu.addSeparator()

            remove_action = QAction("Remove Repository", self)
            remove_action.triggered.connect(lambda: self.remove_repository(repo))
            menu.addAction(remove_action)

        elif item.type() == self.WORKTREE_TYPE:
            worktree = item.data(0, Qt.ItemDataRole.UserRole)
            repo = self.get_selected_repository()

            new_session_action = QAction("New Session", self)
            new_session_action.triggered.connect(
                lambda: self.create_session_requested.emit(worktree)
            )
            menu.addAction(new_session_action)

            if not worktree.is_main and repo:
                menu.addSeparator()
                remove_action = QAction("Remove Worktree", self)
                remove_action.triggered.connect(
                    lambda: self.remove_worktree_requested.emit(repo, worktree)
                )
                menu.addAction(remove_action)

        elif item.type() == self.SESSION_TYPE:
            session = item.data(0, Qt.ItemDataRole.UserRole)

            remove_action = QAction("Remove Session", self)
            remove_action.triggered.connect(
                lambda: self.remove_session_requested.emit(session)
            )
            menu.addAction(remove_action)

        menu.exec(self._tree.mapToGlobal(pos))

    def _refresh_repository(self, repo: Repository) -> None:
        """Refresh a repository's data."""
        try:
            updated = self._git_service.get_repository(repo.path)
            self.update_repository(updated)
        except Exception:
            pass  # Handle error in main window
