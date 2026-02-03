"""Main window for Canopy application."""

from pathlib import Path
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
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
from canopy.models.repository import Repository
from canopy.models.session import Session, SessionStatus

from .dialogs import PermissionDialog
from .session_panel import SessionPanel
from .session_tabs import SessionTabWidget


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, repo_path: Path | None = None) -> None:
        super().__init__()
        self._repo_path = repo_path

        # Load configuration
        self._config = AppConfig.load()

        # Initialize services
        self._git_service = GitService(self)
        self._session_manager = SessionManager(
            claude_command=self._config.claude_command,
            parent=self,
        )

        # Repository data - single repository from current directory
        self._repository: Repository | None = None

        # Track pending worktree operations (worktree_path -> repo_path)
        self._pending_creations: dict[Path, tuple[Path, str]] = {}  # path -> (repo_path, branch)
        self._pending_removals: dict[Path, Path] = {}  # path -> repo_path

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._connect_signals()
        self._restore_geometry()
        self._load_repository()

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

        # Session panel (left sidebar)
        self._session_panel = SessionPanel()
        self._session_panel.setMinimumWidth(200)
        self._session_panel.setMaximumWidth(400)
        self._splitter.addWidget(self._session_panel)

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

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Session menu
        session_menu = menubar.addMenu("&Session")

        new_session_action = QAction("&New Session", self)
        new_session_action.setShortcut(QKeySequence("Ctrl+N"))
        new_session_action.triggered.connect(self._on_create_session)
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
        # Session panel signals
        self._session_panel.create_session_requested.connect(self._on_create_session)
        self._session_panel.session_selected.connect(self._on_session_selected)
        self._session_panel.delete_session_requested.connect(self._on_delete_session)

        # Session tab signals
        self._session_tabs.session_closed.connect(self._on_session_closed)
        self._session_tabs.message_submitted.connect(self._on_message_submitted)
        self._session_tabs.cancel_requested.connect(self._on_cancel_requested)

        # Session manager signals
        self._session_manager.session_created.connect(self._on_session_created)
        self._session_manager.status_changed.connect(self._on_status_changed)

        # Connect tool result signal to refresh diffs
        self._session_manager.tool_result_received.connect(self._on_tool_result)

        # Connect permission request signal
        self._session_manager.permission_requested.connect(self._on_permission_requested)

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

    def _load_repository(self) -> None:
        """Load the repository from the current directory."""
        if not self._repo_path:
            self._statusbar.showMessage("No repository specified")
            return

        try:
            if not self._git_service.is_git_repository(self._repo_path):
                self._statusbar.showMessage(f"Not a Git repository: {self._repo_path}")
                return

            self._repository = self._git_service.get_repository(self._repo_path)
            self.setWindowTitle(f"Canopy - {self._repository.name}")
            self._statusbar.showMessage(f"Repository: {self._repository.name}")

            # Load existing sessions for this repository
            self._load_sessions()
        except GitError as e:
            self._statusbar.showMessage(f"Error loading repository: {e}")

    def _load_sessions(self) -> None:
        """Load sessions for the current repository."""
        if not self._repository:
            return

        # Get all sessions and filter for this repository
        all_sessions = self._session_manager.sessions
        repo_sessions = []

        for session in all_sessions:
            # Check if session's worktree is under this repository
            try:
                # Session worktree_path could be a worktree created for this repo
                session_repo_path = self._get_session_repo_path(session)
                if session_repo_path and session_repo_path == self._repository.path:
                    repo_sessions.append(session)
            except Exception:
                # If we can't determine, include sessions that match the repo path
                if str(self._repository.path) in str(session.worktree_path):
                    repo_sessions.append(session)

        self._session_panel.set_sessions(repo_sessions)

    def _get_session_repo_path(self, session: Session) -> Path | None:
        """Get the main repository path for a session's worktree."""
        try:
            # The worktree path might be the main repo or a worktree
            worktree_path = session.worktree_path
            if self._git_service.is_git_repository(worktree_path):
                # Check if it's a worktree or main repo
                repo = self._git_service.get_repository(worktree_path)
                if repo.main_worktree:
                    return repo.main_worktree.path
        except Exception:
            pass
        return None

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

            # Create session for the new worktree
            if creation_info:
                from datetime import datetime
                session = self._session_manager.create_session(
                    worktree_path=worktree_path,
                    name=f"Session {datetime.now().strftime('%H:%M')}",
                )
                self._session_panel.add_session(session)
                self._session_tabs.add_session(session)
        else:
            self._statusbar.showMessage(f"Failed to create worktree: {message}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create worktree: {message}",
            )

    def _on_worktree_removal_started(self, worktree_path: Path) -> None:
        """Handle worktree removal started."""
        self._statusbar.showMessage(f"Removing worktree: {worktree_path.name}...")

    def _on_worktree_removal_finished(
        self, worktree_path: Path, success: bool, message: str
    ) -> None:
        """Handle worktree removal completion."""
        self._pending_removals.pop(worktree_path, None)

        if success:
            self._statusbar.showMessage(f"Deleted worktree: {worktree_path.name}")
        else:
            self._statusbar.showMessage(f"Failed to delete worktree: {message}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete worktree: {message}",
            )

    def _on_create_session(self) -> None:
        """Handle create session action."""
        if not self._repository:
            QMessageBox.warning(
                self,
                "No Repository",
                "Please run canopy-gui from a Git repository directory.",
            )
            return

        try:
            # Generate a unique session name and branch
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            session_name = f"session-{timestamp}"
            branch_name = f"canopy/{session_name}"

            # Create worktree in {repo_path}.canopy directory (sibling to repo)
            canopy_dir = Path(str(self._repository.path) + ".canopy")
            canopy_dir.mkdir(exist_ok=True)
            worktree_path = canopy_dir / session_name

            # Check if already creating this worktree
            if self._git_service.is_creating_worktree(worktree_path):
                self._statusbar.showMessage("Worktree is already being created...")
                return

            # Get the current branch as base
            current_branch = self._git_service.get_current_branch(self._repository.path)

            # Track the pending creation
            self._pending_creations[worktree_path] = (self._repository.path, branch_name)

            # Start async creation
            self._git_service.create_worktree_async(
                repo_path=self._repository.path,
                worktree_path=worktree_path,
                branch=branch_name,
                create_branch=True,
                base_branch=current_branch,
            )

        except GitError as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create session: {e}",
            )

    def _on_session_selected(self, session: Session) -> None:
        """Handle session selection from session panel."""
        self._session_tabs.add_session(session)

    def _on_delete_session(self, session: Session) -> None:
        """Handle delete session action."""
        reply = QMessageBox.question(
            self,
            "Delete Session",
            f"Delete session '{session.name}'?\n\n"
            "This will also delete the associated worktree and branch.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                worktree_path = session.worktree_path

                # Remove session first
                self._session_manager.remove_session(session.id)
                self._session_tabs.remove_session(session.id)
                self._session_panel.remove_session(session)

                # Delete the worktree if it exists and is not the main repo
                if worktree_path.exists() and self._repository:
                    # Check if already being removed
                    if self._git_service.is_removing_worktree(worktree_path):
                        self._statusbar.showMessage("Worktree is already being removed...")
                        return

                    # Check if this is a worktree (not the main repo)
                    worktrees = self._git_service.list_worktrees(self._repository.path)
                    for wt in worktrees:
                        if wt.path == worktree_path and not wt.is_main:
                            # Track the pending removal
                            self._pending_removals[worktree_path] = self._repository.path

                            # Start async removal
                            self._git_service.remove_worktree_async(
                                repo_path=self._repository.path,
                                worktree_path=worktree_path,
                                delete_directory=True,
                                force=True,
                            )
                            break
                    else:
                        self._statusbar.showMessage("Deleted session")
                else:
                    self._statusbar.showMessage("Deleted session")

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to delete session: {e}",
                )

    def _on_session_created(self, session: Session) -> None:
        """Handle session created signal."""
        self._statusbar.showMessage(f"Created session: {session.name}")

    def _on_session_closed(self, session_id: UUID) -> None:
        """Handle session tab closed."""
        # Just remove from tabs, don't delete the session
        self._session_tabs.remove_session(session_id)

    def _on_message_submitted(
        self, session_id: UUID, message: str, file_refs: list[str] = None, model: str = None
    ) -> None:
        """Handle message submitted from session tab."""
        self._session_manager.send_message(session_id, message, file_refs or [], model)

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

    def _on_permission_requested(
        self, session: Session, request_id: str, tool_name: str, tool_input: dict
    ) -> None:
        """Handle permission request from Claude CLI."""
        dialog = PermissionDialog(tool_name, tool_input, self)

        # Use non-blocking dialog to avoid freezing the UI
        # Connect to response signal to handle the result asynchronously
        def handle_response(response: str) -> None:
            accept = response in (PermissionDialog.ACCEPT, PermissionDialog.ACCEPT_ALWAYS)
            self._session_manager.respond_permission(session.id, accept)
            dialog.deleteLater()

        dialog.response_given.connect(handle_response)
        dialog.setModal(True)  # Keep it modal but non-blocking
        dialog.show()

    def _refresh_session_diff(self, session_id) -> None:
        """Refresh the diff view for a session (no-op, diff viewer removed)."""
        pass

    def _on_close_session(self) -> None:
        """Handle close session menu action."""
        session_id = self._session_tabs.get_current_session_id()
        if session_id:
            self._on_session_closed(session_id)

    def _toggle_sidebar(self) -> None:
        """Toggle the sidebar visibility."""
        if self._session_panel.isVisible():
            self._session_panel.hide()
        else:
            self._session_panel.show()

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
