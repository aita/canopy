"""Session panel widget for the sidebar."""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from canopy.models.session import Session


class SessionListItem(QFrame):
    """A single session item in the session list."""

    clicked = Signal()
    delete_requested = Signal()

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._selected = False
        self._setup_ui()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Session name (from branch or worktree name)
        self._name_label = QLabel(self._session.name)
        self._name_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 500;
            color: #e5e5e5;
        """)
        self._name_label.setWordWrap(True)
        layout.addWidget(self._name_label)

        # Bottom row: repo name and timestamp
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        # Repo/worktree indicator
        repo_name = self._session.worktree_path.parent.name
        self._repo_label = QLabel(repo_name)
        self._repo_label.setStyleSheet("""
            font-size: 11px;
            color: #9ca3af;
        """)
        bottom_layout.addWidget(self._repo_label)

        bottom_layout.addStretch()

        # Timestamp
        time_str = self._session.created_at.strftime("%H:%M")
        self._time_label = QLabel(time_str)
        self._time_label.setStyleSheet("""
            font-size: 11px;
            color: #6b7280;
        """)
        bottom_layout.addWidget(self._time_label)

        layout.addLayout(bottom_layout)

    def _update_style(self) -> None:
        """Update the frame style based on selection state."""
        if self._selected:
            self.setStyleSheet("""
                SessionListItem {
                    background-color: #3b3b3b;
                    border-left: 3px solid #d97706;
                    border-radius: 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                SessionListItem {
                    background-color: transparent;
                    border-left: 3px solid transparent;
                    border-radius: 4px;
                }
                SessionListItem:hover {
                    background-color: #2d2d2d;
                }
            """)

    def set_selected(self, selected: bool) -> None:
        """Set the selection state."""
        self._selected = selected
        self._update_style()

    @property
    def session(self) -> Session:
        """Get the session."""
        return self._session

    def mousePressEvent(self, event) -> None:
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _show_context_menu(self, pos) -> None:
        """Show context menu."""
        menu = QMenu(self)

        delete_action = QAction("Delete Session", self)
        delete_action.triggered.connect(self.delete_requested.emit)
        menu.addAction(delete_action)

        menu.exec(self.mapToGlobal(pos))


class SessionPanel(QWidget):
    """Left sidebar panel showing sessions for the current repository."""

    # Signals
    session_selected = Signal(Session)
    create_session_requested = Signal()
    delete_session_requested = Signal(Session)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sessions: list[Session] = []
        self._session_items: dict[str, SessionListItem] = {}
        self._selected_session_id: str | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #252525;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 12, 12, 12)

        header_label = QLabel("セッション")
        header_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 500;
            color: #9ca3af;
        """)
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        # Settings button (placeholder for future use)
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(24, 24)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #9ca3af;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #e5e5e5;
            }
        """)
        header_layout.addWidget(settings_btn)

        layout.addWidget(header)

        # Scroll area for sessions
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
        """)

        # Container for session items
        self._session_container = QWidget()
        self._session_layout = QVBoxLayout(self._session_container)
        self._session_layout.setContentsMargins(8, 8, 8, 8)
        self._session_layout.setSpacing(4)
        self._session_layout.addStretch()

        scroll_area.setWidget(self._session_container)
        layout.addWidget(scroll_area)

        # New session button at bottom
        button_container = QWidget()
        button_container.setStyleSheet("background-color: #252525;")
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(12, 12, 12, 12)

        self._new_session_btn = QPushButton("+ 新しいセッション")
        self._new_session_btn.setStyleSheet("""
            QPushButton {
                background-color: #d97706;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #b45309;
            }
            QPushButton:pressed {
                background-color: #92400e;
            }
        """)
        self._new_session_btn.clicked.connect(self.create_session_requested.emit)
        button_layout.addWidget(self._new_session_btn)

        layout.addWidget(button_container)

    def set_sessions(self, sessions: list[Session]) -> None:
        """Set the list of sessions."""
        # Clear existing items
        for item in self._session_items.values():
            item.deleteLater()
        self._session_items.clear()

        # Sort sessions by created_at (newest first)
        self._sessions = sorted(sessions, key=lambda s: s.created_at, reverse=True)

        # Remove stretch
        while self._session_layout.count() > 0:
            item = self._session_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new items
        for session in self._sessions:
            item = SessionListItem(session)
            item.clicked.connect(lambda s=session: self._on_session_clicked(s))
            item.delete_requested.connect(
                lambda s=session: self.delete_session_requested.emit(s)
            )
            self._session_items[str(session.id)] = item
            self._session_layout.addWidget(item)

        # Add stretch at the end
        self._session_layout.addStretch()

        # Restore selection
        if self._selected_session_id and self._selected_session_id in self._session_items:
            self._session_items[self._selected_session_id].set_selected(True)

    def add_session(self, session: Session) -> None:
        """Add a single session to the list."""
        self._sessions.insert(0, session)
        self.set_sessions(self._sessions)

    def remove_session(self, session: Session) -> None:
        """Remove a session from the list."""
        self._sessions = [s for s in self._sessions if s.id != session.id]
        self.set_sessions(self._sessions)

    def _on_session_clicked(self, session: Session) -> None:
        """Handle session item click."""
        # Update selection
        if self._selected_session_id and self._selected_session_id in self._session_items:
            self._session_items[self._selected_session_id].set_selected(False)

        self._selected_session_id = str(session.id)
        if self._selected_session_id in self._session_items:
            self._session_items[self._selected_session_id].set_selected(True)

        self.session_selected.emit(session)

    def select_session(self, session: Session) -> None:
        """Programmatically select a session."""
        self._on_session_clicked(session)
