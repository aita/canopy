"""Session tab widget for managing multiple sessions."""

from typing import Optional
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

from .chat_view import SimpleChatView
from .message_input import MessageInput


class SessionTab(QWidget):
    """A single session tab containing chat view and input."""

    message_submitted = Signal(str)
    cancel_requested = Signal()

    def __init__(
        self,
        session: Session,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._setup_ui()
        self._connect_signals()
        self._load_messages()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Session info header - VSCode extension style
        header = QWidget()
        header.setStyleSheet("""
            background-color: palette(window);
            border-bottom: 1px solid #3a3a3a;
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)

        self._branch_label = QLabel()
        self._update_header()
        header_layout.addWidget(self._branch_label)

        header_layout.addStretch()

        self._status_label = QLabel()
        self._update_status()
        header_layout.addWidget(self._status_label)

        layout.addWidget(header)

        # Chat view
        self._chat_view = SimpleChatView()
        self._chat_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._chat_view)

        # Message input
        self._message_input = MessageInput()
        layout.addWidget(self._message_input)

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._message_input.message_submitted.connect(self.message_submitted.emit)
        self._message_input.cancel_requested.connect(self.cancel_requested.emit)

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

    def focus_input(self) -> None:
        """Focus the message input."""
        self._message_input.focus()


class SessionTabWidget(QTabWidget):
    """Tab widget for managing multiple sessions."""

    session_closed = Signal(UUID)
    message_submitted = Signal(UUID, str)
    cancel_requested = Signal(UUID)

    def __init__(
        self,
        session_manager: SessionManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._session_manager = session_manager
        self._tabs: dict[UUID, SessionTab] = {}

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)

        # Placeholder when no tabs
        self._placeholder = QLabel("Select a worktree and create a session to start")
        self._placeholder.setStyleSheet("""
            color: #6b7280;
            padding: 40px;
            font-size: 13px;
        """)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _connect_signals(self) -> None:
        """Connect signals."""
        self.tabCloseRequested.connect(self._on_tab_close_requested)

        # Connect to session manager signals
        self._session_manager.message_received.connect(self._on_message_received)
        self._session_manager.status_changed.connect(self._on_status_changed)

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
            lambda msg: self.message_submitted.emit(session.id, msg)
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

    def get_current_session_id(self) -> Optional[UUID]:
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
            tab.set_status(status)


# Qt already imported at top of file
