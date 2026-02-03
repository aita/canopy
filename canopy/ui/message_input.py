"""Message input widget for sending messages to Claude."""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QFont
from PySide6.QtWidgets import (
    QFrame,
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
    """Widget for inputting and sending messages - VSCode extension style."""

    message_submitted = Signal(str)
    cancel_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._is_processing = False
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        # Input container with border
        input_container = QFrame()
        input_container.setStyleSheet("""
            QFrame {
                border: 1px solid #4a4a4a;
                border-radius: 8px;
                background-color: palette(base);
            }
            QFrame:focus-within {
                border-color: #d97706;
            }
        """)

        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(12, 8, 12, 8)
        input_layout.setSpacing(8)

        # Text input
        self._text_edit = MessageTextEdit()
        self._text_edit.setPlaceholderText("Ask Claude a question...")
        self._text_edit.setMinimumHeight(40)
        self._text_edit.setMaximumHeight(150)
        self._text_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )

        # Use monospace font
        font = QFont("JetBrains Mono", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._text_edit.setFont(font)

        # Remove frame from text edit
        self._text_edit.setFrameStyle(QFrame.Shape.NoFrame)

        input_layout.addWidget(self._text_edit)

        # Button row
        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        # Hint text
        hint_label = QWidget()
        hint_layout = QHBoxLayout(hint_label)
        hint_layout.setContentsMargins(0, 0, 0, 0)
        from PySide6.QtWidgets import QLabel
        hint = QLabel("Enter to send, Shift+Enter for newline")
        hint.setStyleSheet("color: #6b7280; font-size: 10px;")
        hint_layout.addWidget(hint)
        button_row.addWidget(hint_label)

        button_row.addStretch()

        # Cancel button (hidden by default)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
        """)
        self._cancel_btn.setVisible(False)
        button_row.addWidget(self._cancel_btn)

        # Send button
        self._send_btn = QPushButton("Send")
        self._send_btn.setStyleSheet("""
            QPushButton {
                background-color: #d97706;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #b45309;
            }
            QPushButton:pressed {
                background-color: #92400e;
            }
            QPushButton:disabled {
                background-color: #6b7280;
            }
        """)
        self._send_btn.setDefault(True)
        button_row.addWidget(self._send_btn)

        input_layout.addLayout(button_row)
        layout.addWidget(input_container)

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
            self._text_edit.setPlaceholderText("Ask Claude a question...")

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the input."""
        self._text_edit.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

        if not enabled:
            self._text_edit.setPlaceholderText("Select a session to start chatting")
        else:
            self._text_edit.setPlaceholderText("Ask Claude a question...")

    def focus(self) -> None:
        """Focus the text input."""
        self._text_edit.setFocus()

    def get_text(self) -> str:
        """Get the current text."""
        return self._text_edit.toPlainText()

    def set_text(self, text: str) -> None:
        """Set the text."""
        self._text_edit.setPlainText(text)
