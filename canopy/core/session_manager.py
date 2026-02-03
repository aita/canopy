"""Session manager for Claude Code sessions."""

import json
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QObject, Signal

from canopy.models.config import get_sessions_dir
from canopy.models.session import Message, MessageRole, Session, SessionStatus

from .claude_runner import ClaudeResponse, ClaudeRunner, StreamEvent


class SessionManager(QObject):
    """Manages Claude Code sessions for worktrees."""

    # Signals
    session_created = Signal(Session)
    session_removed = Signal(UUID)
    session_updated = Signal(Session)
    message_received = Signal(Session, Message)
    status_changed = Signal(Session, SessionStatus)

    # Stream-json signals
    stream_event_received = Signal(Session, object)  # StreamEvent
    streaming_text = Signal(Session, str)  # Incremental text
    tool_use_started = Signal(Session, str, dict)  # tool_name, input
    tool_result_received = Signal(Session, str, str)  # tool_name, result
    permission_requested = Signal(Session, str, str, dict)  # request_id, tool_name, input

    def __init__(
        self,
        claude_command: str = "claude",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sessions: dict[UUID, Session] = {}
        self._runners: dict[UUID, ClaudeRunner] = {}
        self._claude_command = claude_command
        # Store last message params for retry with --allowedTools
        self._pending_messages: dict[UUID, dict] = {}  # session_id -> {message, file_refs, model}
        # Store pending permission requests
        self._pending_permissions: dict[UUID, dict] = {}  # session_id -> {tool_name, tool_input}

        # Load saved sessions
        self._load_sessions()

    @property
    def sessions(self) -> list[Session]:
        """Get all sessions."""
        return list(self._sessions.values())

    def get_session(self, session_id: UUID) -> Session | None:
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
        name: str | None = None,
        base_branch: str | None = None,
    ) -> Session:
        """Create a new session for a worktree."""
        session = Session(worktree_path=worktree_path, base_branch=base_branch)
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

    def send_message(
        self,
        session_id: UUID,
        message: str,
        file_references: list[str] | None = None,
        model: str | None = None,
        allowed_tools: list[str] | None = None,
        add_user_message: bool = True,
    ) -> None:
        """Send a message to a session.

        Args:
            session_id: The session ID
            message: The message to send
            file_references: Optional list of file references to include
            model: Model ID to use (optional)
            allowed_tools: List of pre-approved tool patterns (for permission retry)
            add_user_message: Whether to add the message to chat history
        """
        session = self._sessions.get(session_id)
        if not session:
            return

        runner = self._runners.get(session_id)
        if not runner:
            runner = self._create_runner(session)

        if runner.is_running:
            return  # Already processing

        # Build message with file references
        full_message = message
        if file_references:
            refs = "\n".join(f"@{ref}" for ref in file_references)
            full_message = f"{refs}\n\n{message}"

        # Store message params for potential retry with --allowedTools
        self._pending_messages[session_id] = {
            "message": message,
            "full_message": full_message,
            "file_references": file_references,
            "model": model,
        }

        # Add user message to session (skip on retry)
        if add_user_message:
            user_msg = session.add_message(MessageRole.USER, message)
            self.message_received.emit(session, user_msg)

        # Update status
        session.status = SessionStatus.RUNNING
        self.status_changed.emit(session, SessionStatus.RUNNING)

        # Send to Claude using stream-json format
        runner.send_message(
            message=full_message,
            cwd=session.worktree_path,
            output_format="stream-json",
            resume_session=session.claude_session_id,
            model=model,
            allowed_tools=allowed_tools,
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

        # Connect stream-json signals
        runner.stream_event.connect(
            lambda event: self._on_stream_event(session.id, event)
        )
        runner.assistant_text.connect(
            lambda text: self._on_assistant_text(session.id, text)
        )
        runner.tool_use_started.connect(
            lambda name, inp: self._on_tool_use(session.id, name, inp)
        )
        runner.tool_result_received.connect(
            lambda name, result: self._on_tool_result(session.id, name, result)
        )
        runner.permission_requested.connect(
            lambda req_id, name, inp: self._on_permission_request(session.id, req_id, name, inp)
        )

        self._runners[session.id] = runner
        return runner

    def _on_stream_event(self, session_id: UUID, event: StreamEvent) -> None:
        """Handle a stream event."""
        session = self._sessions.get(session_id)
        if session:
            self.stream_event_received.emit(session, event)

            # Update session ID from init event
            if event.type == "init" and event.session_id:
                session.claude_session_id = event.session_id

    def _on_assistant_text(self, session_id: UUID, text: str) -> None:
        """Handle streaming assistant text."""
        session = self._sessions.get(session_id)
        if session:
            self.streaming_text.emit(session, text)

    def _on_tool_use(self, session_id: UUID, tool_name: str, tool_input: dict) -> None:
        """Handle tool use event."""
        session = self._sessions.get(session_id)
        if session:
            self.tool_use_started.emit(session, tool_name, tool_input)

    def _on_tool_result(self, session_id: UUID, tool_name: str, result: str) -> None:
        """Handle tool result event."""
        session = self._sessions.get(session_id)
        if session:
            self.tool_result_received.emit(session, tool_name, result)

    def _on_permission_request(
        self, session_id: UUID, request_id: str, tool_name: str, tool_input: dict
    ) -> None:
        """Handle permission request event."""
        session = self._sessions.get(session_id)
        if session:
            # Store permission info for potential retry
            self._pending_permissions[session_id] = {
                "request_id": request_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
            }
            self.permission_requested.emit(session, request_id, tool_name, tool_input)

    def respond_permission(self, session_id: UUID, accept: bool) -> None:
        """Respond to a permission request.

        If accepted, re-run the last message with --allowedTools for the denied tool.
        If rejected, just clear the pending permission.

        Args:
            session_id: The session ID
            accept: True to accept, False to reject
        """
        perm = self._pending_permissions.pop(session_id, None)
        if not perm:
            return

        if not accept:
            return  # Just ignore rejection

        # Build the tool pattern for --allowedTools
        tool_name = perm["tool_name"]
        tool_input = perm["tool_input"]

        # Create a tool pattern that allows this specific command
        # Format: "ToolName(pattern)" or just "ToolName" for full access
        if tool_name == "Bash":
            cmd = tool_input.get("command", "")
            # Use exact command as pattern (escape special chars if needed)
            tool_pattern = f"Bash({cmd})"
        elif tool_name in ("Read", "Write", "Edit"):
            path = tool_input.get("file_path", "")
            tool_pattern = f"{tool_name}({path})"
        else:
            # For other tools, allow the entire tool
            tool_pattern = tool_name

        # Get the pending message and re-send with --allowedTools
        pending = self._pending_messages.get(session_id)
        if pending:
            self.send_message(
                session_id=session_id,
                message=pending["message"],
                file_references=pending["file_references"],
                model=pending["model"],
                allowed_tools=[tool_pattern],
                add_user_message=False,  # Don't add duplicate user message
            )

    def _on_response(self, session_id: UUID, response: dict) -> None:
        """Handle a response from Claude."""
        session = self._sessions.get(session_id)
        if not session:
            return

        parsed = ClaudeResponse(response)

        # Update session ID for future --resume
        if parsed.session_id:
            session.claude_session_id = parsed.session_id

        # Only add assistant message for "result" type events to avoid duplicates.
        # Both "assistant" and "result" events contain the same content,
        # so we only process the final "result" event.
        if parsed.is_result:
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

        # Reset status to IDLE so the input is re-enabled
        if session.status == SessionStatus.RUNNING:
            session.status = SessionStatus.IDLE
            self.status_changed.emit(session, SessionStatus.IDLE)
            self._save_sessions()

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

    def get_runner(self, session_id: UUID) -> ClaudeRunner | None:
        """Get the runner for a session."""
        return self._runners.get(session_id)
