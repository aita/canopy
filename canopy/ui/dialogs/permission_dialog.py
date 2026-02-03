"""Dialog for tool permission requests from Claude CLI."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class PermissionDialog(QDialog):
    """Dialog for approving tool executions from Claude CLI."""

    # Signal emitted when user responds (response_code: str)
    # This allows non-blocking dialog usage with dialog.show()
    response_given = Signal(str)

    # Response codes
    ACCEPT = "accept"
    REJECT = "reject"
    ACCEPT_ALWAYS = "accept_always"

    def __init__(
        self,
        tool_name: str,
        tool_input: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tool_name = tool_name
        self._tool_input = tool_input
        self._response = self.REJECT
        self._response_emitted = False  # Track if signal was already emitted

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setWindowTitle("Permission Request")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel(f"Claude wants to use: <b>{self._tool_name}</b>")
        header.setStyleSheet("font-size: 14px;")
        layout.addWidget(header)

        # Tool input display
        input_label = QLabel("Input:")
        input_label.setStyleSheet("color: #9ca3af; font-size: 11px; margin-top: 8px;")
        layout.addWidget(input_label)

        # Scrollable area for tool input
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                background-color: #1e1e1e;
            }
        """)

        input_content = QWidget()
        input_layout = QVBoxLayout(input_content)
        input_layout.setContentsMargins(8, 8, 8, 8)

        # Format tool input
        input_text = self._format_tool_input()
        input_display = QLabel(input_text)
        input_display.setWordWrap(True)
        input_display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        input_display.setStyleSheet("""
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: #e5e7eb;
        """)
        input_layout.addWidget(input_display)
        input_layout.addStretch()

        scroll.setWidget(input_content)
        layout.addWidget(scroll, 1)

        # Button row
        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        button_row.addStretch()

        # Reject button
        self._reject_btn = QPushButton("Reject")
        self._reject_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
        """)
        button_row.addWidget(self._reject_btn)

        # Accept button
        self._accept_btn = QPushButton("Accept")
        self._accept_btn.setStyleSheet("""
            QPushButton {
                background-color: #d97706;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #b45309;
            }
            QPushButton:pressed {
                background-color: #92400e;
            }
        """)
        self._accept_btn.setDefault(True)
        button_row.addWidget(self._accept_btn)

        # Accept Always button
        self._accept_always_btn = QPushButton("Accept Always")
        self._accept_always_btn.setToolTip("Accept this tool for the rest of the session")
        self._accept_always_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
            QPushButton:pressed {
                background-color: #15803d;
            }
        """)
        button_row.addWidget(self._accept_always_btn)

        layout.addLayout(button_row)

    def _format_tool_input(self) -> str:
        """Format tool input for display."""
        if not self._tool_input:
            return "(no input)"

        lines = []
        for key, value in self._tool_input.items():
            if isinstance(value, str) and len(value) > 500:
                # Truncate long values
                value = value[:500] + "..."
            lines.append(f"<b>{key}:</b> {value}")
        return "<br>".join(lines)

    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        self._reject_btn.clicked.connect(self._on_reject)
        self._accept_btn.clicked.connect(self._on_accept)
        self._accept_always_btn.clicked.connect(self._on_accept_always)

    def _emit_response(self, response: str) -> None:
        """Emit response signal only once."""
        if not self._response_emitted:
            self._response_emitted = True
            self._response = response
            self.response_given.emit(response)

    def _on_reject(self) -> None:
        """Handle reject button."""
        self._emit_response(self.REJECT)
        self.reject()

    def _on_accept(self) -> None:
        """Handle accept button."""
        self._emit_response(self.ACCEPT)
        self.accept()

    def _on_accept_always(self) -> None:
        """Handle accept always button."""
        self._emit_response(self.ACCEPT_ALWAYS)
        self.accept()

    def closeEvent(self, event) -> None:
        """Handle dialog close event (X button or Escape key)."""
        # Emit reject response if dialog is closed without explicit button click
        self._emit_response(self.REJECT)
        super().closeEvent(event)

    def get_response(self) -> str:
        """Get the user's response."""
        return self._response
