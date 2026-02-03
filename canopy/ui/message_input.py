"""Message input widget for sending messages to Claude."""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class MessageTextEdit(QTextEdit):
    """Text edit that sends on Enter (without Shift)."""

    submit_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.submit_requested.emit()
        else:
            super().keyPressEvent(event)


class MessageInput(QWidget):
    """Widget for inputting and sending messages."""

    message_submitted = Signal(str)
    cancel_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._is_processing = False
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Text input
        self._text_edit = MessageTextEdit()
        self._text_edit.setPlaceholderText("Type your message... (Enter to send, Shift+Enter for newline)")
        self._text_edit.setMaximumHeight(100)
        self._text_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self._text_edit)

        # Button container
        button_layout = QVBoxLayout()
        button_layout.setSpacing(4)

        # Send button
        self._send_btn = QPushButton("Send")
        self._send_btn.setMinimumWidth(80)
        self._send_btn.setDefault(True)
        button_layout.addWidget(self._send_btn)

        # Cancel button (hidden by default)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setMinimumWidth(80)
        self._cancel_btn.setVisible(False)
        button_layout.addWidget(self._cancel_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        self._text_edit.submit_requested.connect(self._on_submit)
        self._send_btn.clicked.connect(self._on_submit)
        self._cancel_btn.clicked.connect(self._on_cancel)

    def _on_submit(self) -> None:
        """Handle submit action."""
        if self._is_processing:
            return

        text = self._text_edit.toPlainText().strip()
        if text:
            self.message_submitted.emit(text)
            self._text_edit.clear()

    def _on_cancel(self) -> None:
        """Handle cancel action."""
        self.cancel_requested.emit()

    def set_processing(self, processing: bool) -> None:
        """Set the processing state."""
        self._is_processing = processing
        self._text_edit.setEnabled(not processing)
        self._send_btn.setEnabled(not processing)
        self._send_btn.setVisible(not processing)
        self._cancel_btn.setVisible(processing)

        if processing:
            self._text_edit.setPlaceholderText("Claude is thinking...")
        else:
            self._text_edit.setPlaceholderText(
                "Type your message... (Enter to send, Shift+Enter for newline)"
            )

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the input."""
        self._text_edit.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

        if not enabled:
            self._text_edit.setPlaceholderText("Select a session to start chatting")
        else:
            self._text_edit.setPlaceholderText(
                "Type your message... (Enter to send, Shift+Enter for newline)"
            )

    def focus(self) -> None:
        """Focus the text input."""
        self._text_edit.setFocus()

    def get_text(self) -> str:
        """Get the current text."""
        return self._text_edit.toPlainText()

    def set_text(self, text: str) -> None:
        """Set the text."""
        self._text_edit.setPlainText(text)
