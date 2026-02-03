"""Chat view widget for displaying conversation history."""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
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


class MessageBubble(QFrame):
    """A single message bubble in the chat."""

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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Role label
        role_label = QLabel(self._get_role_display())
        role_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        layout.addWidget(role_label)

        # Content
        content = QTextEdit()
        content.setReadOnly(True)
        content.setPlainText(self._message.content)
        content.setFrameStyle(QFrame.Shape.NoFrame)
        content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Auto-resize to content
        content.document().setDocumentMargin(0)
        content.setMinimumHeight(20)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        # Calculate height based on content
        doc = content.document()
        doc.setTextWidth(content.viewport().width())
        height = int(doc.size().height()) + 10
        content.setFixedHeight(min(height, 400))  # Max height

        layout.addWidget(content)

        # Timestamp
        time_label = QLabel(self._message.timestamp.strftime("%H:%M"))
        time_label.setStyleSheet("color: gray; font-size: 10px;")
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(time_label)

        # Style based on role
        self._apply_style()

    def _get_role_display(self) -> str:
        """Get display name for role."""
        if self._message.role == MessageRole.USER:
            return "You"
        elif self._message.role == MessageRole.ASSISTANT:
            return "Claude"
        else:
            return "System"

    def _apply_style(self) -> None:
        """Apply style based on message role."""
        if self._message.role == MessageRole.USER:
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #e3f2fd;
                    border-radius: 8px;
                    margin-left: 40px;
                }
            """)
        elif self._message.role == MessageRole.ASSISTANT:
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #f5f5f5;
                    border-radius: 8px;
                    margin-right: 40px;
                }
            """)
        else:  # System
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #fff3e0;
                    border-radius: 8px;
                    margin-left: 20px;
                    margin-right: 20px;
                }
            """)


class ChatView(QWidget):
    """Widget for displaying chat history."""

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
        self._container_layout.setContentsMargins(8, 8, 8, 8)
        self._container_layout.setSpacing(8)
        self._container_layout.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

        # Welcome message when empty
        self._welcome_label = QLabel("Start a conversation with Claude")
        self._welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._welcome_label.setStyleSheet("color: gray; padding: 40px;")
        font = QFont()
        font.setPointSize(14)
        self._welcome_label.setFont(font)

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()

        # Remove all message bubbles
        while self._container_layout.count() > 1:  # Keep the stretch
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_message(self, message: Message) -> None:
        """Add a message to the chat."""
        self._messages.append(message)

        # Insert before the stretch
        bubble = MessageBubble(message)
        self._container_layout.insertWidget(
            self._container_layout.count() - 1, bubble
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
        # Use a slight delay to ensure layout is updated
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(10, self._do_scroll_to_bottom)

    def _do_scroll_to_bottom(self) -> None:
        """Actually scroll to bottom."""
        scrollbar = self._scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


class SimpleChatView(QWidget):
    """Simpler chat view using a single text widget."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Monospace", 11))

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
            cursor.insertHtml(
                f'<p style="color: #1976d2;"><b>You</b> '
                f'<span style="color: gray; font-size: 10px;">'
                f'{message.timestamp.strftime("%H:%M")}</span></p>'
            )
        elif message.role == MessageRole.ASSISTANT:
            cursor.insertHtml(
                f'<p style="color: #388e3c;"><b>Claude</b> '
                f'<span style="color: gray; font-size: 10px;">'
                f'{message.timestamp.strftime("%H:%M")}</span></p>'
            )
        else:
            cursor.insertHtml(
                f'<p style="color: #f57c00;"><b>System</b></p>'
            )

        # Add content
        cursor.insertText(message.content + "\n\n")

        # Scroll to bottom
        self._text.moveCursor(QTextCursor.MoveOperation.End)

    def set_messages(self, messages: list[Message]) -> None:
        """Set all messages at once."""
        self.clear()
        for msg in messages:
            self.add_message(msg)
