"""Session manager for Claude Code sessions."""

import json
from pathlib import Path
from typing import Optional
from uuid import UUID

from PySide6.QtCore import QObject, Signal

from canopy.models.config import get_sessions_dir
from canopy.models.session import Message, MessageRole, Session, SessionStatus

from .claude_runner import ClaudeResponse, ClaudeRunner


class SessionManager(QObject):
    """Manages Claude Code sessions for worktrees."""

    # Signals
    session_created = Signal(Session)
    session_removed = Signal(UUID)
    session_updated = Signal(Session)
    message_received = Signal(Session, Message)
    status_changed = Signal(Session, SessionStatus)

    def __init__(
        self,
        claude_command: str = "claude",
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._sessions: dict[UUID, Session] = {}
        self._runners: dict[UUID, ClaudeRunner] = {}
        self._claude_command = claude_command

        # Load saved sessions
        self._load_sessions()

    @property
    def sessions(self) -> list[Session]:
        """Get all sessions."""
        return list(self._sessions.values())

    def get_session(self, session_id: UUID) -> Optional[Session]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_sessions_for_worktree(self, worktree_path: Path) -> list[Session]:
        """Get all sessions for a specific worktree."""
        return [
            s for s in self._sessions.values()
            if s.worktree_path == worktree_path
        ]

    def create_session(
        self,
        worktree_path: Path,
        name: Optional[str] = None,
    ) -> Session:
        """Create a new session for a worktree."""
        session = Session(worktree_path=worktree_path)
        if name:
            session.name = name

        self._sessions[session.id] = session
        self._create_runner(session)
        self._save_sessions()

        self.session_created.emit(session)
        return session

    def remove_session(self, session_id: UUID) -> None:
        """Remove a session."""
        session = self._sessions.get(session_id)
        if not session:
            return

        # Stop the runner if running
        runner = self._runners.get(session_id)
        if runner and runner.is_running:
            runner.cancel()

        # Remove runner
        if session_id in self._runners:
            self._runners[session_id].deleteLater()
            del self._runners[session_id]

        # Remove session
        del self._sessions[session_id]
        self._save_sessions()

        self.session_removed.emit(session_id)

    def remove_sessions_for_worktree(self, worktree_path: Path) -> None:
        """Remove all sessions for a worktree."""
        sessions = self.get_sessions_for_worktree(worktree_path)
        for session in sessions:
            self.remove_session(session.id)

    def send_message(self, session_id: UUID, message: str) -> None:
        """Send a message to a session."""
        session = self._sessions.get(session_id)
        if not session:
            return

        runner = self._runners.get(session_id)
        if not runner:
            runner = self._create_runner(session)

        if runner.is_running:
            return  # Already processing

        # Add user message to session
        user_msg = session.add_message(MessageRole.USER, message)
        self.message_received.emit(session, user_msg)

        # Update status
        session.status = SessionStatus.RUNNING
        self.status_changed.emit(session, SessionStatus.RUNNING)

        # Send to Claude
        runner.send_message(
            message=message,
            cwd=session.worktree_path,
            output_format="json",
            resume_session=session.claude_session_id,
        )

    def cancel_request(self, session_id: UUID) -> None:
        """Cancel the current request for a session."""
        runner = self._runners.get(session_id)
        if runner:
            runner.cancel()

    def _create_runner(self, session: Session) -> ClaudeRunner:
        """Create a runner for a session."""
        runner = ClaudeRunner(
            claude_command=self._claude_command,
            parent=self,
        )

        # Connect signals
        runner.response_received.connect(
            lambda resp: self._on_response(session.id, resp)
        )
        runner.error_occurred.connect(
            lambda err: self._on_error(session.id, err)
        )
        runner.process_finished.connect(
            lambda code: self._on_finished(session.id, code)
        )

        self._runners[session.id] = runner
        return runner

    def _on_response(self, session_id: UUID, response: dict) -> None:
        """Handle a response from Claude."""
        session = self._sessions.get(session_id)
        if not session:
            return

        parsed = ClaudeResponse(response)

        # Update session ID for future --resume
        if parsed.session_id:
            session.claude_session_id = parsed.session_id

        # Extract and add assistant message
        content = parsed.content
        if content:
            msg = session.add_message(MessageRole.ASSISTANT, content)
            self.message_received.emit(session, msg)

        self._save_sessions()
        self.session_updated.emit(session)

    def _on_error(self, session_id: UUID, error: str) -> None:
        """Handle an error from Claude."""
        session = self._sessions.get(session_id)
        if not session:
            return

        # Add error as system message
        msg = session.add_message(MessageRole.SYSTEM, f"Error: {error}")
        self.message_received.emit(session, msg)

    def _on_finished(self, session_id: UUID, exit_code: int) -> None:
        """Handle process completion."""
        session = self._sessions.get(session_id)
        if not session:
            return

        session.status = SessionStatus.IDLE
        self.status_changed.emit(session, SessionStatus.IDLE)
        self._save_sessions()

    def _get_sessions_file(self) -> Path:
        """Get the sessions file path."""
        return get_sessions_dir() / "sessions.json"

    def _save_sessions(self) -> None:
        """Save sessions to disk."""
        sessions_file = self._get_sessions_file()
        data = {
            "sessions": [s.to_dict() for s in self._sessions.values()]
        }
        with open(sessions_file, "w") as f:
            json.dump(data, f, indent=2)

    def _load_sessions(self) -> None:
        """Load sessions from disk."""
        sessions_file = self._get_sessions_file()
        if not sessions_file.exists():
            return

        try:
            with open(sessions_file) as f:
                data = json.load(f)

            for session_data in data.get("sessions", []):
                session = Session.from_dict(session_data)
                # Only load sessions for existing worktrees
                if session.worktree_path.exists():
                    session.status = SessionStatus.IDLE
                    self._sessions[session.id] = session
        except (json.JSONDecodeError, KeyError):
            pass  # Ignore corrupted sessions file

    def get_runner(self, session_id: UUID) -> Optional[ClaudeRunner]:
        """Get the runner for a session."""
        return self._runners.get(session_id)
