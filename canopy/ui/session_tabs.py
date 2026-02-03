"""Session tab widget for managing multiple sessions."""

from pathlib import Path
from uuid import UUID

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from canopy.core.session_manager import SessionManager
from canopy.models.session import Message, Session, SessionStatus

from .chat_view import StreamingChatView
from .file_reference import FileReferencePanel
from .message_input import MessageInput


class SessionTab(QWidget):
    """A single session tab containing chat view and message input."""

    message_submitted = Signal(str, list, str)  # message, file_references, model
    cancel_requested = Signal()

    def __init__(
        self,
        session: Session,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._is_streaming = False
        self._setup_ui()
        self._connect_signals()
        self._load_messages()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Session info header - compact style
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet("""
            background-color: #1e1e1e;
            border-bottom: 1px solid #3a3a3a;
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)

        self._branch_label = QLabel()
        self._update_header()
        header_layout.addWidget(self._branch_label)

        header_layout.addStretch()

        self._status_label = QLabel()
        self._update_status()
        header_layout.addWidget(self._status_label)

        layout.addWidget(header)

        # Chat view (streaming enabled)
        self._chat_view = StreamingChatView()
        self._chat_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._chat_view)

        # File references panel (collapsible)
        self._file_reference_panel = FileReferencePanel()
        self._file_reference_panel.set_worktree(self._session.worktree_path)
        self._file_reference_panel.setMaximumHeight(150)
        self._file_reference_panel.setVisible(False)  # Hidden by default
        layout.addWidget(self._file_reference_panel)

        # Message input
        self._message_input = MessageInput()
        layout.addWidget(self._message_input)

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._message_input.message_submitted.connect(self._on_message_submitted)
        self._message_input.cancel_requested.connect(self.cancel_requested.emit)
        self._message_input.attach_files_requested.connect(self.toggle_file_references)

    def _on_message_submitted(self, message: str, model: str) -> None:
        """Handle message submission with file references and model."""
        refs = self._file_reference_panel.get_references()
        self.message_submitted.emit(message, refs, model)

    def _load_messages(self) -> None:
        """Load existing messages into the chat view."""
        self._chat_view.set_messages(self._session.messages)

    def _update_header(self) -> None:
        """Update the header info."""
        branch = self._session.worktree_path.name
        self._branch_label.setText(branch)
        self._branch_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 500;
        """)
        self._branch_label.setToolTip(str(self._session.worktree_path))

    def _update_status(self) -> None:
        """Update the status display."""
        if self._session.status == SessionStatus.RUNNING:
            self._status_label.setText("Processing...")
            self._status_label.setStyleSheet("""
                color: #d97706;
                font-size: 11px;
                font-weight: 500;
            """)
        elif self._session.status == SessionStatus.IDLE:
            self._status_label.setText("Ready")
            self._status_label.setStyleSheet("""
                color: #22c55e;
                font-size: 11px;
                font-weight: 500;
            """)
        else:
            self._status_label.setText("Stopped")
            self._status_label.setStyleSheet("""
                color: #6b7280;
                font-size: 11px;
                font-weight: 500;
            """)

    @property
    def session(self) -> Session:
        """Get the session."""
        return self._session

    def add_message(self, message: Message) -> None:
        """Add a message to the chat view."""
        self._chat_view.add_message(message)

    def set_status(self, status: SessionStatus) -> None:
        """Set the session status."""
        self._session.status = status
        self._update_status()
        self._message_input.set_processing(status == SessionStatus.RUNNING)

    def start_streaming(self) -> None:
        """Start streaming mode for assistant response."""
        self._is_streaming = True
        self._chat_view.start_streaming()

    def append_streaming_text(self, text: str) -> None:
        """Append text to streaming response."""
        if self._is_streaming:
            self._chat_view.append_streaming_text(text)

    def finish_streaming(self) -> None:
        """Finish streaming mode."""
        if self._is_streaming:
            self._is_streaming = False
            self._chat_view.finish_streaming()

    def add_tool_use(self, tool_name: str, tool_input: dict) -> None:
        """Add a tool use entry (no-op, command log removed)."""
        pass

    def add_tool_result(self, tool_name: str, result: str) -> None:
        """Add a tool result (no-op, command log removed)."""
        pass

    def toggle_file_references(self) -> None:
        """Toggle file references panel visibility."""
        self._file_reference_panel.setVisible(
            not self._file_reference_panel.isVisible()
        )

    def add_file_reference(self, file_path: Path) -> None:
        """Add a file reference."""
        self._file_reference_panel.add_file(file_path)

    def focus_input(self) -> None:
        """Focus the message input."""
        self._message_input.focus()


class SessionTabWidget(QTabWidget):
    """Tab widget for managing multiple sessions."""

    session_closed = Signal(UUID)
    message_submitted = Signal(UUID, str, list, str)  # session_id, message, file_refs, model
    cancel_requested = Signal(UUID)

    def __init__(
        self,
        session_manager: SessionManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_manager = session_manager
        self._tabs: dict[UUID, SessionTab] = {}
        self._streaming_sessions: set[UUID] = set()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #9ca3af;
                padding: 8px 16px;
                border: none;
                border-right: 1px solid #3a3a3a;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QTabBar::tab:hover {
                background-color: #3a3a3a;
            }
        """)

        # Placeholder when no tabs
        self._placeholder = QLabel("Select a worktree and create a session to start")
        self._placeholder.setStyleSheet("""
            color: #6b7280;
            padding: 40px;
            font-size: 13px;
            background-color: #1e1e1e;
        """)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _connect_signals(self) -> None:
        """Connect signals."""
        self.tabCloseRequested.connect(self._on_tab_close_requested)

        # Connect to session manager signals
        self._session_manager.message_received.connect(self._on_message_received)
        self._session_manager.status_changed.connect(self._on_status_changed)

        # Connect stream-json signals
        self._session_manager.streaming_text.connect(self._on_streaming_text)
        self._session_manager.tool_use_started.connect(self._on_tool_use)
        self._session_manager.tool_result_received.connect(self._on_tool_result)

    def add_session(self, session: Session) -> SessionTab:
        """Add a session tab."""
        if session.id in self._tabs:
            # Switch to existing tab
            tab = self._tabs[session.id]
            self.setCurrentWidget(tab)
            return tab

        # Create new tab
        tab = SessionTab(session)
        tab.message_submitted.connect(
            lambda msg, refs, model: self.message_submitted.emit(session.id, msg, refs, model)
        )
        tab.cancel_requested.connect(
            lambda: self.cancel_requested.emit(session.id)
        )

        self._tabs[session.id] = tab
        index = self.addTab(tab, session.name)
        self.setCurrentIndex(index)
        tab.focus_input()

        return tab

    def remove_session(self, session_id: UUID) -> None:
        """Remove a session tab."""
        tab = self._tabs.get(session_id)
        if tab:
            index = self.indexOf(tab)
            if index >= 0:
                self.removeTab(index)
            del self._tabs[session_id]
            tab.deleteLater()

    def get_current_session_id(self) -> UUID | None:
        """Get the current session ID."""
        tab = self.currentWidget()
        if isinstance(tab, SessionTab):
            return tab.session.id
        return None

    def switch_to_session(self, session_id: UUID) -> None:
        """Switch to a session tab."""
        tab = self._tabs.get(session_id)
        if tab:
            self.setCurrentWidget(tab)
            tab.focus_input()

    def _on_tab_close_requested(self, index: int) -> None:
        """Handle tab close request."""
        tab = self.widget(index)
        if isinstance(tab, SessionTab):
            self.session_closed.emit(tab.session.id)

    def _on_message_received(self, session: Session, message: Message) -> None:
        """Handle message received from session manager."""
        tab = self._tabs.get(session.id)
        if tab:
            tab.add_message(message)

    def _on_status_changed(self, session: Session, status: SessionStatus) -> None:
        """Handle status change from session manager."""
        tab = self._tabs.get(session.id)
        if tab:
            # Start streaming when running starts
            if status == SessionStatus.RUNNING:
                if session.id not in self._streaming_sessions:
                    self._streaming_sessions.add(session.id)
                    tab.start_streaming()
            else:
                # Finish streaming when status changes from running
                if session.id in self._streaming_sessions:
                    self._streaming_sessions.discard(session.id)
                    tab.finish_streaming()

            tab.set_status(status)

    def _on_streaming_text(self, session: Session, text: str) -> None:
        """Handle streaming text from Claude."""
        tab = self._tabs.get(session.id)
        if tab and session.id in self._streaming_sessions:
            tab.append_streaming_text(text)

    def _on_tool_use(self, session: Session, tool_name: str, tool_input: dict) -> None:
        """Handle tool use event."""
        tab = self._tabs.get(session.id)
        if tab:
            tab.add_tool_use(tool_name, tool_input)

    def _on_tool_result(self, session: Session, tool_name: str, result: str) -> None:
        """Handle tool result event."""
        tab = self._tabs.get(session.id)
        if tab:
            tab.add_tool_result(tool_name, result)

    def get_tab(self, session_id: UUID) -> SessionTab | None:
        """Get a session tab by ID."""
        return self._tabs.get(session_id)
