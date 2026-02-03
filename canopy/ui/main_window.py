"""Main window for Canopy application."""

from pathlib import Path
from typing import Optional
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from canopy.core.git_service import GitError, GitService
from canopy.core.session_manager import SessionManager
from canopy.models.config import AppConfig
from canopy.models.repository import Repository, Worktree
from canopy.models.session import Session, SessionStatus

from .dialogs import AddRepoDialog, CreateWorktreeDialog
from .session_tabs import SessionTabWidget
from .worktree_panel import WorktreePanel


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()

        # Load configuration
        self._config = AppConfig.load()

        # Initialize services
        self._git_service = GitService(self)
        self._session_manager = SessionManager(
            claude_command=self._config.claude_command,
            parent=self,
        )

        # Repository data
        self._repositories: dict[Path, Repository] = {}

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._connect_signals()
        self._restore_geometry()
        self._load_repositories()

    def _setup_ui(self) -> None:
        """Set up the main UI."""
        self.setWindowTitle("Canopy - Claude Code Worktree IDE")

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Worktree panel (left sidebar)
        self._worktree_panel = WorktreePanel(self._git_service)
        self._worktree_panel.setMinimumWidth(200)
        self._worktree_panel.setMaximumWidth(400)
        self._splitter.addWidget(self._worktree_panel)

        # Session tabs (main area)
        self._session_tabs = SessionTabWidget(self._session_manager)
        self._splitter.addWidget(self._session_tabs)

        # Set splitter sizes
        self._splitter.setSizes(self._config.splitter_sizes)

        layout.addWidget(self._splitter)

    def _setup_menu(self) -> None:
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        add_repo_action = QAction("&Add Repository...", self)
        add_repo_action.setShortcut(QKeySequence("Ctrl+O"))
        add_repo_action.triggered.connect(self._on_add_repository)
        file_menu.addAction(add_repo_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Session menu
        session_menu = menubar.addMenu("&Session")

        new_session_action = QAction("&New Session", self)
        new_session_action.setShortcut(QKeySequence("Ctrl+N"))
        new_session_action.triggered.connect(self._on_new_session)
        session_menu.addAction(new_session_action)

        close_session_action = QAction("&Close Session", self)
        close_session_action.setShortcut(QKeySequence("Ctrl+W"))
        close_session_action.triggered.connect(self._on_close_session)
        session_menu.addAction(close_session_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        toggle_sidebar_action = QAction("Toggle &Sidebar", self)
        toggle_sidebar_action.setShortcut(QKeySequence("Ctrl+B"))
        toggle_sidebar_action.triggered.connect(self._toggle_sidebar)
        view_menu.addAction(toggle_sidebar_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_statusbar(self) -> None:
        """Set up the status bar."""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready")

    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        # Worktree panel signals
        self._worktree_panel.add_repository_requested.connect(self._on_add_repository)
        self._worktree_panel.unregister_repository_requested.connect(
            self._on_unregister_repository
        )
        self._worktree_panel.create_worktree_requested.connect(
            self._on_create_worktree
        )
        self._worktree_panel.delete_worktree_requested.connect(
            self._on_delete_worktree
        )
        self._worktree_panel.create_session_requested.connect(
            self._on_create_session
        )
        self._worktree_panel.session_selected.connect(self._on_session_selected)
        self._worktree_panel.remove_session_requested.connect(
            self._on_remove_session
        )

        # Session tab signals
        self._session_tabs.session_closed.connect(self._on_session_closed)
        self._session_tabs.message_submitted.connect(self._on_message_submitted)
        self._session_tabs.cancel_requested.connect(self._on_cancel_requested)

        # Session manager signals
        self._session_manager.session_created.connect(self._on_session_created)
        self._session_manager.status_changed.connect(self._on_status_changed)

    def _restore_geometry(self) -> None:
        """Restore window geometry from config."""
        self.resize(self._config.window_width, self._config.window_height)
        if self._config.window_x is not None and self._config.window_y is not None:
            self.move(self._config.window_x, self._config.window_y)

    def _save_geometry(self) -> None:
        """Save window geometry to config."""
        self._config.window_width = self.width()
        self._config.window_height = self.height()
        self._config.window_x = self.x()
        self._config.window_y = self.y()
        self._config.splitter_sizes = self._splitter.sizes()
        self._config.save()

    def _load_repositories(self) -> None:
        """Load saved repositories."""
        for repo_path in self._config.repositories:
            path = Path(repo_path)
            if path.exists():
                try:
                    repo = self._git_service.get_repository(path)
                    self._repositories[path] = repo
                    self._worktree_panel.add_repository(repo)
                    self._update_sessions_for_repository(repo)
                except GitError as e:
                    self._statusbar.showMessage(f"Error loading {path}: {e}")

    def _update_sessions_for_repository(self, repo: Repository) -> None:
        """Update sessions display for all worktrees in a repository."""
        for worktree in repo.worktrees:
            sessions = self._session_manager.get_sessions_for_worktree(worktree.path)
            self._worktree_panel.set_sessions(worktree.path, sessions)

    def _on_add_repository(self) -> None:
        """Handle add repository action."""
        dialog = AddRepoDialog(self._git_service, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            path = dialog.get_repository_path()
            if path and path not in self._repositories:
                try:
                    repo = self._git_service.get_repository(path)
                    self._repositories[path] = repo
                    self._worktree_panel.add_repository(repo)
                    self._config.add_repository(str(path))
                    self._statusbar.showMessage(f"Added repository: {repo.name}")
                except GitError as e:
                    QMessageBox.critical(
                        self,
                        "Error",
                        f"Failed to add repository: {e}",
                    )

    def _on_create_worktree(self, repo: Repository) -> None:
        """Handle create worktree action."""
        dialog = CreateWorktreeDialog(repo, self._git_service, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_worktree_config()
            try:
                worktree = self._git_service.create_worktree(
                    repo_path=repo.path,
                    worktree_path=config["path"],
                    branch=config["branch"],
                    create_branch=config["create_branch"],
                    base_branch=config["base_branch"],
                )
                # Refresh repository
                updated_repo = self._git_service.get_repository(repo.path)
                self._repositories[repo.path] = updated_repo
                self._worktree_panel.update_repository(updated_repo)
                self._statusbar.showMessage(f"Created worktree: {worktree.branch}")
            except GitError as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to create worktree: {e}",
                )

    def _on_unregister_repository(self, repo: Repository) -> None:
        """Handle unregister repository action."""
        reply = QMessageBox.question(
            self,
            "Unregister Repository",
            f"Unregister '{repo.name}' from Canopy?\n\n"
            "The repository will not be deleted from disk.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Remove sessions for all worktrees
            for worktree in repo.worktrees:
                self._session_manager.remove_sessions_for_worktree(worktree.path)

            # Remove from tracking
            if repo.path in self._repositories:
                del self._repositories[repo.path]
            self._config.remove_repository(str(repo.path))
            self._worktree_panel.remove_repository(repo)
            self._statusbar.showMessage(f"Unregistered repository: {repo.name}")

    def _on_delete_worktree(self, repo: Repository, worktree: Worktree) -> None:
        """Handle delete worktree action."""
        reply = QMessageBox.question(
            self,
            "Delete Worktree",
            f"Delete the worktree '{worktree.branch}'?\n\n"
            f"Path: {worktree.path}\n\n"
            "WARNING: This will delete the worktree directory from disk!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Remove sessions first
                self._session_manager.remove_sessions_for_worktree(worktree.path)

                # Remove worktree
                self._git_service.remove_worktree(repo.path, worktree.path)

                # Refresh repository
                updated_repo = self._git_service.get_repository(repo.path)
                self._repositories[repo.path] = updated_repo
                self._worktree_panel.update_repository(updated_repo)
                self._statusbar.showMessage(f"Deleted worktree: {worktree.branch}")
            except GitError as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to delete worktree: {e}",
                )

    def _on_create_session(self, worktree: Worktree) -> None:
        """Handle create session action."""
        session = self._session_manager.create_session(worktree.path)
        self._session_tabs.add_session(session)
        self._worktree_panel.set_sessions(
            worktree.path,
            self._session_manager.get_sessions_for_worktree(worktree.path),
        )

    def _on_session_selected(self, session: Session) -> None:
        """Handle session selection from worktree panel."""
        self._session_tabs.add_session(session)

    def _on_remove_session(self, session: Session) -> None:
        """Handle remove session action."""
        self._session_manager.remove_session(session.id)
        self._session_tabs.remove_session(session.id)
        self._worktree_panel.set_sessions(
            session.worktree_path,
            self._session_manager.get_sessions_for_worktree(session.worktree_path),
        )

    def _on_session_created(self, session: Session) -> None:
        """Handle session created signal."""
        self._statusbar.showMessage(f"Created session: {session.name}")

    def _on_session_closed(self, session_id: UUID) -> None:
        """Handle session tab closed."""
        # Just remove from tabs, don't delete the session
        self._session_tabs.remove_session(session_id)

    def _on_message_submitted(self, session_id: UUID, message: str) -> None:
        """Handle message submitted from session tab."""
        self._session_manager.send_message(session_id, message)

    def _on_cancel_requested(self, session_id: UUID) -> None:
        """Handle cancel request from session tab."""
        self._session_manager.cancel_request(session_id)

    def _on_status_changed(self, session: Session, status: SessionStatus) -> None:
        """Handle session status change."""
        if status == SessionStatus.RUNNING:
            self._statusbar.showMessage("Processing...")
        else:
            self._statusbar.showMessage("Ready")

    def _on_new_session(self) -> None:
        """Handle new session menu action."""
        worktree = self._worktree_panel.get_selected_worktree()
        if worktree:
            self._on_create_session(worktree)
        else:
            self._statusbar.showMessage("Please select a worktree first")

    def _on_close_session(self) -> None:
        """Handle close session menu action."""
        session_id = self._session_tabs.get_current_session_id()
        if session_id:
            self._on_session_closed(session_id)

    def _toggle_sidebar(self) -> None:
        """Toggle the sidebar visibility."""
        if self._worktree_panel.isVisible():
            self._worktree_panel.hide()
        else:
            self._worktree_panel.show()

    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Canopy",
            "<h2>Canopy</h2>"
            "<p>Claude Code Worktree IDE</p>"
            "<p>Version 0.1.0</p>"
            "<p>A desktop application for managing Git worktrees "
            "and Claude Code sessions.</p>",
        )

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        self._save_geometry()
        event.accept()
