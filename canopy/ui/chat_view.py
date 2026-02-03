"""Chat view widget for displaying conversation history."""

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor, QPalette, QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from canopy.models.session import Message, MessageRole


class MessageWidget(QFrame):
    """A single message in the chat - VSCode extension style."""

    def __init__(
        self,
        message: Message,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._message = message
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Role indicator (icon-like)
        role_indicator = QLabel(self._get_role_icon())
        role_indicator.setFixedSize(28, 28)
        role_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        role_indicator.setStyleSheet(self._get_role_style())
        layout.addWidget(role_indicator, 0, Qt.AlignmentFlag.AlignTop)

        # Content area
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        # Role name and timestamp
        header = QLabel(f"{self._get_role_name()}  ·  {self._message.timestamp.strftime('%H:%M')}")
        header.setStyleSheet("font-size: 11px; opacity: 0.7;")
        content_layout.addWidget(header)

        # Message content
        content = QTextEdit()
        content.setReadOnly(True)
        content.setPlainText(self._message.content)
        content.setFrameStyle(QFrame.Shape.NoFrame)
        content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Use monospace font for better code display
        font = QFont("JetBrains Mono", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        content.setFont(font)

        # Auto-resize to content
        content.document().setDocumentMargin(0)
        content.setMinimumHeight(24)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        # Calculate height based on content
        doc = content.document()
        doc.setTextWidth(600)  # Max width for content
        height = int(doc.size().height()) + 8
        content.setFixedHeight(min(height, 600))  # Max height

        content_layout.addWidget(content)
        layout.addLayout(content_layout, 1)

    def _get_role_icon(self) -> str:
        """Get icon character for role."""
        if self._message.role == MessageRole.USER:
            return "U"
        elif self._message.role == MessageRole.ASSISTANT:
            return "C"
        else:
            return "!"

    def _get_role_name(self) -> str:
        """Get display name for role."""
        if self._message.role == MessageRole.USER:
            return "You"
        elif self._message.role == MessageRole.ASSISTANT:
            return "Claude"
        else:
            return "System"

    def _get_role_style(self) -> str:
        """Get style for role indicator."""
        if self._message.role == MessageRole.USER:
            return """
                background-color: #4a4a4a;
                color: white;
                border-radius: 14px;
                font-weight: bold;
                font-size: 12px;
            """
        elif self._message.role == MessageRole.ASSISTANT:
            return """
                background-color: #d97706;
                color: white;
                border-radius: 14px;
                font-weight: bold;
                font-size: 12px;
            """
        else:
            return """
                background-color: #dc2626;
                color: white;
                border-radius: 14px;
                font-weight: bold;
                font-size: 12px;
            """


class ChatView(QWidget):
    """Widget for displaying chat history - VSCode extension style."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._messages: list[Message] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameStyle(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container for messages
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 8, 0, 8)
        self._container_layout.setSpacing(0)
        self._container_layout.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()

        # Remove all message widgets
        while self._container_layout.count() > 1:  # Keep the stretch
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_message(self, message: Message) -> None:
        """Add a message to the chat."""
        self._messages.append(message)

        # Insert before the stretch
        widget = MessageWidget(message)
        self._container_layout.insertWidget(
            self._container_layout.count() - 1, widget
        )

        # Scroll to bottom
        self._scroll_to_bottom()

    def set_messages(self, messages: list[Message]) -> None:
        """Set all messages at once."""
        self.clear()
        for msg in messages:
            self.add_message(msg)

    def _scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the chat."""
        QTimer.singleShot(10, self._do_scroll_to_bottom)

    def _do_scroll_to_bottom(self) -> None:
        """Actually scroll to bottom."""
        scrollbar = self._scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


class SimpleChatView(QWidget):
    """Simple text-based chat view - VSCode extension style."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._text = QTextEdit()
        self._text.setReadOnly(True)

        # Use monospace font
        font = QFont("JetBrains Mono", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._text.setFont(font)

        # Remove frame for cleaner look
        self._text.setFrameStyle(QFrame.Shape.NoFrame)

        layout.addWidget(self._text)

    def clear(self) -> None:
        """Clear all messages."""
        self._text.clear()

    def add_message(self, message: Message) -> None:
        """Add a message to the chat."""
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Format based on role
        if message.role == MessageRole.USER:
            role_prefix = "You"
            role_color = "#6b7280"
        elif message.role == MessageRole.ASSISTANT:
            role_prefix = "Claude"
            role_color = "#d97706"
        else:
            role_prefix = "System"
            role_color = "#dc2626"

        # Insert formatted message with HTML
        timestamp = message.timestamp.strftime('%H:%M')
        html = f"""
        <div style="margin: 8px 12px; padding: 0;">
            <div style="margin-bottom: 4px;">
                <span style="color: {role_color}; font-weight: bold;">{role_prefix}</span>
                <span style="color: #9ca3af; font-size: 10px; margin-left: 8px;">{timestamp}</span>
            </div>
            <div style="white-space: pre-wrap; margin-left: 0;">{self._escape_html(message.content)}</div>
        </div>
        <hr style="border: none; border-top: 1px solid #374151; margin: 8px 0;">
        """
        cursor.insertHtml(html)

        # Scroll to bottom
        self._text.moveCursor(QTextCursor.MoveOperation.End)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )

    def set_messages(self, messages: list[Message]) -> None:
        """Set all messages at once."""
        self.clear()
        for msg in messages:
            self.add_message(msg)
