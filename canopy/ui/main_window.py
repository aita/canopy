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

from .dialogs import AddRepoDialog, CreateWorktreeDialog, DeleteWorktreeDialog
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

        # Track pending worktree operations (worktree_path -> repo_path)
        self._pending_creations: dict[Path, tuple[Path, str]] = {}  # path -> (repo_path, branch)
        self._pending_removals: dict[Path, Path] = {}  # path -> repo_path

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

        # Connect tool result signal to refresh diffs
        self._session_manager.tool_result_received.connect(self._on_tool_result)

        # Git service signals for async operations
        self._git_service.worktree_creation_started.connect(
            self._on_worktree_creation_started
        )
        self._git_service.worktree_creation_finished.connect(
            self._on_worktree_creation_finished
        )
        self._git_service.worktree_removal_started.connect(
            self._on_worktree_removal_started
        )
        self._git_service.worktree_removal_finished.connect(
            self._on_worktree_removal_finished
        )

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
            worktree_path = config["path"]

            # Check if already creating this worktree
            if self._git_service.is_creating_worktree(worktree_path):
                self._statusbar.showMessage("Worktree is already being created...")
                return

            # Track the pending creation
            self._pending_creations[worktree_path] = (repo.path, config["branch"])

            # Start async creation
            self._git_service.create_worktree_async(
                repo_path=repo.path,
                worktree_path=worktree_path,
                branch=config["branch"],
                create_branch=config["create_branch"],
                base_branch=config["base_branch"],
            )

    def _on_worktree_creation_started(self, worktree_path: Path) -> None:
        """Handle worktree creation started."""
        self._statusbar.showMessage(f"Creating worktree: {worktree_path.name}...")

    def _on_worktree_creation_finished(
        self, worktree_path: Path, success: bool, message: str
    ) -> None:
        """Handle worktree creation completion."""
        creation_info = self._pending_creations.pop(worktree_path, None)

        if success:
            branch = creation_info[1] if creation_info else worktree_path.name
            self._statusbar.showMessage(f"Created worktree: {branch}")
            # Refresh repository
            if creation_info:
                repo_path = creation_info[0]
                if repo_path in self._repositories:
                    try:
                        updated_repo = self._git_service.get_repository(repo_path)
                        self._repositories[repo_path] = updated_repo
                        self._worktree_panel.update_repository(updated_repo)
                    except GitError:
                        pass
        else:
            self._statusbar.showMessage(f"Failed to create worktree: {message}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create worktree: {message}",
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
        # Check if already being removed
        if self._git_service.is_removing_worktree(worktree.path):
            self._statusbar.showMessage("Worktree is already being removed...")
            return

        # Show deletion mode dialog
        dialog = DeleteWorktreeDialog(worktree, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        deletion_mode = dialog.get_deletion_mode()
        delete_directory = deletion_mode == DeleteWorktreeDialog.DELETE_DIRECTORY

        # Remove sessions first
        self._session_manager.remove_sessions_for_worktree(worktree.path)

        # Track the pending removal
        self._pending_removals[worktree.path] = repo.path

        # Start async removal
        self._git_service.remove_worktree_async(
            repo_path=repo.path,
            worktree_path=worktree.path,
            delete_directory=delete_directory,
        )

    def _on_worktree_removal_started(self, worktree_path: Path) -> None:
        """Handle worktree removal started."""
        self._statusbar.showMessage(f"Removing worktree: {worktree_path.name}...")

    def _on_worktree_removal_finished(
        self, worktree_path: Path, success: bool, message: str
    ) -> None:
        """Handle worktree removal completion."""
        repo_path = self._pending_removals.pop(worktree_path, None)

        if success:
            self._statusbar.showMessage(f"Deleted worktree: {worktree_path.name}")
            # Refresh repository
            if repo_path and repo_path in self._repositories:
                try:
                    updated_repo = self._git_service.get_repository(repo_path)
                    self._repositories[repo_path] = updated_repo
                    self._worktree_panel.update_repository(updated_repo)
                except GitError:
                    pass
        else:
            self._statusbar.showMessage(f"Failed to delete worktree: {message}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete worktree: {message}",
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

    def _on_message_submitted(
        self, session_id: UUID, message: str, file_refs: list[str] = None
    ) -> None:
        """Handle message submitted from session tab."""
        self._session_manager.send_message(session_id, message, file_refs or [])

    def _on_cancel_requested(self, session_id: UUID) -> None:
        """Handle cancel request from session tab."""
        self._session_manager.cancel_request(session_id)

    def _on_status_changed(self, session: Session, status: SessionStatus) -> None:
        """Handle session status change."""
        if status == SessionStatus.RUNNING:
            self._statusbar.showMessage("Processing...")
        else:
            self._statusbar.showMessage("Ready")
            # Refresh diff view when Claude finishes
            self._refresh_session_diff(session.id)

    def _on_tool_result(self, session: Session, tool_name: str, result: str) -> None:
        """Handle tool result - refresh diffs if file was modified."""
        # Refresh diff view when file operations complete
        if tool_name in ("Write", "Edit", "Bash"):
            self._refresh_session_diff(session.id)

    def _refresh_session_diff(self, session_id) -> None:
        """Refresh the diff view for a session (no-op, diff viewer removed)."""
        pass

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
