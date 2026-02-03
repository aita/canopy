"""Chat view widget for displaying conversation history."""

from io import StringIO

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from canopy.models.session import Message, MessageRole


class InlineDiffHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for inline diff content."""

    def __init__(self, parent: QTextDocument) -> None:
        super().__init__(parent)

        # Format for added lines
        self._add_format = QTextCharFormat()
        self._add_format.setBackground(QColor("#1e3a29"))
        self._add_format.setForeground(QColor("#4ade80"))

        # Format for deleted lines
        self._del_format = QTextCharFormat()
        self._del_format.setBackground(QColor("#3f1d1d"))
        self._del_format.setForeground(QColor("#f87171"))

        # Format for hunk headers
        self._hunk_format = QTextCharFormat()
        self._hunk_format.setForeground(QColor("#60a5fa"))

        # Format for file headers
        self._header_format = QTextCharFormat()
        self._header_format.setForeground(QColor("#9ca3af"))

    def highlightBlock(self, text: str) -> None:
        """Highlight a block of text."""
        if text.startswith("+") and not text.startswith("+++"):
            self.setFormat(0, len(text), self._add_format)
        elif text.startswith("-") and not text.startswith("---"):
            self.setFormat(0, len(text), self._del_format)
        elif text.startswith("@@"):
            self.setFormat(0, len(text), self._hunk_format)
        elif text.startswith("---") or text.startswith("+++"):
            self.setFormat(0, len(text), self._header_format)


class InlineDiffPreviewWidget(QFrame):
    """Inline diff preview widget with collapsible view."""

    # Default number of lines to show when collapsed
    DEFAULT_COLLAPSED_LINES = 8

    def __init__(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        tool_name: str = "Edit",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._file_path = file_path
        self._old_string = old_string
        self._new_string = new_string
        self._tool_name = tool_name
        self._diff_lines: list[str] = []
        self._is_expanded = False
        self._collapsed_lines = self.DEFAULT_COLLAPSED_LINES
        self._setup_ui()
        self._generate_diff()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            InlineDiffPreviewWidget {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                margin: 4px 16px 4px 56px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with file path
        self._header = QFrame()
        self._header.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border-bottom: 1px solid #3a3a3a;
            }
        """)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)

        # Tool icon based on operation
        icon = "✏️" if self._tool_name == "Edit" else "📝"
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 12px;")
        header_layout.addWidget(icon_label)

        # File path
        path_label = QLabel(self._file_path)
        path_label.setStyleSheet("""
            color: #e5e5e5;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
        """)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header_layout.addWidget(path_label)

        header_layout.addStretch()

        layout.addWidget(self._header)

        # Diff content area
        self._diff_text = QTextEdit()
        self._diff_text.setReadOnly(True)
        self._diff_text.setFrameStyle(QFrame.Shape.NoFrame)
        self._diff_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._diff_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._diff_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                padding: 8px;
            }
        """)

        # Monospace font
        font = QFont("JetBrains Mono", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._diff_text.setFont(font)

        # Apply highlighter
        self._highlighter = InlineDiffHighlighter(self._diff_text.document())

        layout.addWidget(self._diff_text)

        # Expand button (shown when collapsed and more lines available)
        self._expand_button = QPushButton()
        self._expand_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #60a5fa;
                border: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                color: #93c5fd;
            }
        """)
        self._expand_button.clicked.connect(self._toggle_expand)
        self._expand_button.setVisible(False)
        layout.addWidget(self._expand_button)

    def _generate_diff(self) -> None:
        """Generate unified diff from old and new strings."""
        import difflib

        old_lines = self._old_string.splitlines(keepends=True)
        new_lines = self._new_string.splitlines(keepends=True)

        # Ensure lines end with newline for diff formatting
        if old_lines and not old_lines[-1].endswith('\n'):
            old_lines[-1] += '\n'
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] += '\n'

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="original",
            tofile="modified",
            lineterm=""
        )

        self._diff_lines = [line.rstrip('\n') for line in diff]
        self._update_display()

    def _update_display(self) -> None:
        """Update the diff display based on collapsed/expanded state."""
        if not self._diff_lines:
            self._diff_text.setPlainText("No changes")
            self._expand_button.setVisible(False)
            self._update_height()
            return

        total_lines = len(self._diff_lines)

        if self._is_expanded or total_lines <= self._collapsed_lines:
            # Show all lines
            display_lines = self._diff_lines
            self._expand_button.setVisible(False)
        else:
            # Show collapsed view
            display_lines = self._diff_lines[:self._collapsed_lines]
            remaining = total_lines - self._collapsed_lines
            self._expand_button.setText(f"▼ Show full diff ({remaining} more lines)")
            self._expand_button.setVisible(True)

        self._diff_text.setPlainText('\n'.join(display_lines))
        self._update_height()

    def _update_height(self) -> None:
        """Update height based on content."""
        doc = self._diff_text.document()
        doc.setDocumentMargin(8)
        # Calculate height based on line count
        line_height = self._diff_text.fontMetrics().lineSpacing()
        visible_lines = self._diff_text.toPlainText().count('\n') + 1
        content_height = line_height * visible_lines + 24  # Add padding
        # Cap at reasonable max height
        max_height = 400 if self._is_expanded else 200
        self._diff_text.setFixedHeight(min(content_height, max_height))

    def _toggle_expand(self) -> None:
        """Toggle between collapsed and expanded view."""
        self._is_expanded = not self._is_expanded
        if self._is_expanded:
            self._expand_button.setText("▲ Collapse diff")
        self._update_display()


class MessageWidget(QFrame):
    """A single message in the chat - VSCode extension style."""

    def __init__(
        self,
        message: Message,
        parent: QWidget | None = None,
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

    def __init__(self, parent: QWidget | None = None) -> None:
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


class StreamingChatView(QWidget):
    """Chat view with streaming support - VSCode extension style."""

    # Thinking indicators like Claude CLI
    THINKING_WORDS = ["*hmm*", "*thonk*", "*ponders*", "*thinking*", "*processing*"]

    # Signals for permission responses
    permission_accepted = Signal(str)  # request_id
    permission_rejected = Signal(str)  # request_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._messages: list[Message] = []
        self._streaming_buffer = StringIO()
        self._is_streaming = False
        self._has_content = False
        self._thinking_index = 0
        self._permission_widget: QWidget | None = None
        self._current_permission_id: str | None = None
        self._thinking_timer: QTimer | None = None
        self._streaming_widget: StreamingMessageWidget | None = None
        # Store pending permission request to show after streaming finishes
        self._pending_permission: dict | None = None
        # Store pending edit operation to show diff preview
        self._pending_edit: dict | None = None
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
        self._scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a4a;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        # Container for messages
        self._container = QWidget()
        self._container.setStyleSheet("background-color: #1e1e1e;")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 8, 0, 8)
        self._container_layout.setSpacing(0)
        self._container_layout.addStretch()

        # Thinking indicator at the bottom (separate from messages)
        self._thinking_indicator = QLabel()
        self._thinking_indicator.setStyleSheet("""
            QLabel {
                color: #d97706;
                font-size: 12px;
                font-style: italic;
                padding: 8px 16px;
                background-color: transparent;
            }
        """)
        self._thinking_indicator.setVisible(False)
        self._container_layout.addWidget(self._thinking_indicator)

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()
        self._streaming_buffer = StringIO()
        self._is_streaming = False
        self._pending_permission = None
        self._pending_edit = None
        self._hide_thinking_indicator()
        self._remove_permission_widget()

        # Remove all message widgets (keep stretch and thinking indicator)
        while self._container_layout.count() > 2:
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_message(self, message: Message) -> None:
        """Add a message to the chat."""
        self._messages.append(message)

        # Create and insert widget (before stretch and thinking indicator)
        widget = StreamingMessageWidget(message)
        self._container_layout.insertWidget(
            self._container_layout.count() - 2, widget
        )

        self._scroll_to_bottom()

    def start_streaming(self) -> None:
        """Start streaming mode for assistant response."""
        self._is_streaming = True
        self._streaming_buffer = StringIO()
        self._thinking_index = 0
        self._has_content = False

        # Show thinking indicator immediately (separate from message)
        self._thinking_indicator.setText(self.THINKING_WORDS[0])
        self._thinking_indicator.setVisible(True)

        # Start timer to rotate thinking words
        if self._thinking_timer:
            self._thinking_timer.stop()
        self._thinking_timer = QTimer(self)
        self._thinking_timer.timeout.connect(self._rotate_thinking)
        self._thinking_timer.start(1500)  # Rotate every 1.5 seconds

        self._scroll_to_bottom()

    def _rotate_thinking(self) -> None:
        """Rotate through thinking words."""
        if self._is_streaming and not self._has_content:
            self._thinking_index = (self._thinking_index + 1) % len(self.THINKING_WORDS)
            self._thinking_indicator.setText(self.THINKING_WORDS[self._thinking_index])

    def _hide_thinking_indicator(self) -> None:
        """Hide the thinking indicator."""
        self._thinking_indicator.setVisible(False)
        if self._thinking_timer:
            self._thinking_timer.stop()
            self._thinking_timer = None

    def append_streaming_text(self, text: str) -> None:
        """Append text to the streaming message."""
        if not self._is_streaming:
            return

        # Create streaming widget on first content
        if not self._has_content:
            self._has_content = True
            self._hide_thinking_indicator()
            self._streaming_widget = StreamingMessageWidget(streaming=True)
            # Insert before the thinking indicator (which is at the end)
            self._container_layout.insertWidget(
                self._container_layout.count() - 2, self._streaming_widget
            )

        self._streaming_buffer.write(text)
        self._streaming_widget.set_content(self._streaming_buffer.getvalue())
        self._scroll_to_bottom()

    def show_tool_use(self, tool_name: str, tool_input: dict) -> None:
        """Show tool use info in the thinking indicator."""
        if not self._is_streaming:
            return

        # Store edit operation for diff preview
        if tool_name == "Edit":
            self._pending_edit = {
                "tool_name": tool_name,
                "file_path": tool_input.get("file_path", ""),
                "old_string": tool_input.get("old_string", ""),
                "new_string": tool_input.get("new_string", ""),
            }

        # Format tool description for the thinking indicator
        if tool_name == "Bash":
            cmd = tool_input.get("command", "")
            desc = tool_input.get("description", "")
            if desc:
                tool_desc = f"`{cmd}` ({desc})"
            else:
                tool_desc = f"`{cmd}`"
        elif tool_name in ("Read", "Write", "Edit"):
            path = tool_input.get("file_path", "")
            tool_desc = f"{tool_name}: {path}"
        elif tool_name in ("Glob", "Grep"):
            pattern = tool_input.get("pattern", "")
            tool_desc = f"{tool_name}: {pattern}"
        else:
            tool_desc = tool_name

        # Get next thinking word
        self._thinking_index = (self._thinking_index + 1) % len(self.THINKING_WORDS)
        thinking = self.THINKING_WORDS[self._thinking_index]

        # Update thinking indicator with tool info
        self._thinking_indicator.setText(f"{thinking} {tool_desc}")
        self._thinking_indicator.setVisible(True)
        self._scroll_to_bottom()

    def show_tool_result(self, tool_name: str, result: str) -> None:
        """Show tool result - show diff preview for Edit operations."""
        if not self._is_streaming:
            return

        # Show diff preview for Edit operations
        if tool_name == "Edit" and self._pending_edit:
            edit_info = self._pending_edit
            self._pending_edit = None

            # Create diff preview widget
            diff_widget = InlineDiffPreviewWidget(
                file_path=edit_info["file_path"],
                old_string=edit_info["old_string"],
                new_string=edit_info["new_string"],
                tool_name=edit_info["tool_name"],
            )

            # Insert before thinking indicator
            self._container_layout.insertWidget(
                self._container_layout.count() - 2, diff_widget
            )
            self._scroll_to_bottom()

    def show_permission_request(
        self, request_id: str, tool_name: str, tool_input: dict
    ) -> None:
        """Store permission request to show after streaming finishes."""
        # Store the request to show after streaming completes
        self._pending_permission = {
            "request_id": request_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
        }

        # Update thinking indicator to show permission is pending
        self._thinking_indicator.setText("⚠️ Permission required...")
        self._thinking_indicator.setVisible(True)

    def _show_permission_buttons(self) -> None:
        """Actually show the permission request UI with buttons."""
        if not self._pending_permission:
            return

        request_id = self._pending_permission["request_id"]
        tool_name = self._pending_permission["tool_name"]
        tool_input = self._pending_permission["tool_input"]

        # Remove existing permission widget if any
        self._remove_permission_widget()
        self._current_permission_id = request_id

        # Format tool description and command display
        if tool_name == "Bash":
            cmd = tool_input.get("command", "")
            desc = tool_input.get("description", "")
            if desc:
                tool_desc = f"{desc}"
                cmd_display = cmd
            else:
                tool_desc = "Bash command"
                cmd_display = cmd
        elif tool_name in ("Read", "Write", "Edit"):
            path = tool_input.get("file_path", "")
            tool_desc = f"{tool_name} file"
            cmd_display = path
        else:
            tool_desc = tool_name
            cmd_display = str(tool_input)

        # Create permission widget with command display and buttons
        self._permission_widget = QFrame()
        self._permission_widget.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #d97706;
                border-radius: 6px;
                margin: 8px 16px;
                padding: 12px;
            }
        """)

        perm_layout = QVBoxLayout(self._permission_widget)
        perm_layout.setContentsMargins(12, 12, 12, 12)
        perm_layout.setSpacing(12)

        # Title
        title_label = QLabel(f"⚠️ Permission required: {tool_desc}")
        title_label.setStyleSheet("""
            QLabel {
                color: #d97706;
                font-size: 13px;
                font-weight: bold;
            }
        """)
        perm_layout.addWidget(title_label)

        # Command display
        cmd_label = QLabel(cmd_display)
        cmd_label.setStyleSheet("""
            QLabel {
                color: #e5e5e5;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                background-color: #1a1a1a;
                padding: 8px 12px;
                border-radius: 4px;
            }
        """)
        cmd_label.setWordWrap(True)
        cmd_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        perm_layout.addWidget(cmd_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        accept_btn = QPushButton("Accept")
        accept_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
        """)
        accept_btn.clicked.connect(self._on_accept_permission)

        reject_btn = QPushButton("Reject")
        reject_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        reject_btn.clicked.connect(self._on_reject_permission)

        btn_layout.addStretch()
        btn_layout.addWidget(accept_btn)
        btn_layout.addWidget(reject_btn)
        btn_layout.addStretch()

        perm_layout.addLayout(btn_layout)

        # Clear pending permission
        self._pending_permission = None

        # Insert before thinking indicator (at count - 2)
        self._container_layout.insertWidget(
            self._container_layout.count() - 2, self._permission_widget
        )
        self._scroll_to_bottom()

    def _on_accept_permission(self) -> None:
        """Handle accept button click."""
        if self._current_permission_id:
            self.permission_accepted.emit(self._current_permission_id)
        self._remove_permission_widget()

    def _on_reject_permission(self) -> None:
        """Handle reject button click."""
        if self._current_permission_id:
            self.permission_rejected.emit(self._current_permission_id)
        self._remove_permission_widget()

    def _remove_permission_widget(self) -> None:
        """Remove the permission widget."""
        if self._permission_widget:
            self._permission_widget.deleteLater()
            self._permission_widget = None
        self._current_permission_id = None

    def finish_streaming(self) -> Message:
        """Finish streaming and convert to regular message."""
        self._is_streaming = False
        self._hide_thinking_indicator()

        content = self._streaming_buffer.getvalue()
        self._streaming_buffer = StringIO()

        if hasattr(self, "_streaming_widget") and self._streaming_widget:
            self._streaming_widget.finish_streaming()

        # Show permission buttons if there's a pending request
        if self._pending_permission:
            self._show_permission_buttons()

        # Create message from streamed content
        msg = Message(role=MessageRole.ASSISTANT, content=content)
        self._messages.append(msg)
        return msg

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


class StreamingMessageWidget(QFrame):
    """A message widget that supports streaming updates."""

    def __init__(
        self,
        message: Message | None = None,
        streaming: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._message = message
        self._streaming = streaming
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setFrameStyle(QFrame.Shape.NoFrame)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Role indicator
        if self._message:
            role = self._message.role
        else:
            role = MessageRole.ASSISTANT  # Streaming is always assistant

        role_indicator = QLabel(self._get_role_icon(role))
        role_indicator.setFixedSize(32, 32)
        role_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        role_indicator.setStyleSheet(self._get_role_style(role))
        layout.addWidget(role_indicator, 0, Qt.AlignmentFlag.AlignTop)

        # Content area
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        # Header
        if self._message:
            timestamp = self._message.timestamp.strftime('%H:%M')
        else:
            timestamp = "..."

        role_name = self._get_role_name(role)
        header = QLabel(f"{role_name}  ·  {timestamp}")
        header.setStyleSheet("font-size: 11px; color: #6b7280;")
        content_layout.addWidget(header)

        # Content text
        self._content = QTextEdit()
        self._content.setReadOnly(True)
        self._content.setFrameStyle(QFrame.Shape.NoFrame)
        self._content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #d4d4d4;
            }
        """)

        # Monospace font
        font = QFont("JetBrains Mono", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._content.setFont(font)

        # Set content
        if self._message:
            self._content.setPlainText(self._message.content)
        elif self._streaming:
            self._content.setPlainText("▌")  # Cursor indicator

        # Auto-resize
        self._content.document().setDocumentMargin(0)
        self._content.setMinimumHeight(24)
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._update_height()

        content_layout.addWidget(self._content)
        layout.addLayout(content_layout, 1)

    def _get_role_icon(self, role: MessageRole) -> str:
        """Get icon for role."""
        if role == MessageRole.USER:
            return "U"
        elif role == MessageRole.ASSISTANT:
            return "C"
        else:
            return "!"

    def _get_role_name(self, role: MessageRole) -> str:
        """Get display name for role."""
        if role == MessageRole.USER:
            return "You"
        elif role == MessageRole.ASSISTANT:
            return "Claude"
        else:
            return "System"

    def _get_role_style(self, role: MessageRole) -> str:
        """Get style for role indicator."""
        if role == MessageRole.USER:
            return """
                background-color: #4a4a4a;
                color: white;
                border-radius: 16px;
                font-weight: bold;
                font-size: 12px;
            """
        elif role == MessageRole.ASSISTANT:
            return """
                background-color: #d97706;
                color: white;
                border-radius: 16px;
                font-weight: bold;
                font-size: 12px;
            """
        else:
            return """
                background-color: #dc2626;
                color: white;
                border-radius: 16px;
                font-weight: bold;
                font-size: 12px;
            """

    def set_content(self, content: str) -> None:
        """Set the content (for streaming updates)."""
        # Add cursor indicator when streaming
        display_text = content + "▌" if self._streaming else content
        self._content.setPlainText(display_text)
        self._update_height()

    def finish_streaming(self) -> None:
        """Finish streaming mode."""
        self._streaming = False
        # Remove cursor indicator
        text = self._content.toPlainText()
        if text.endswith("▌"):
            text = text[:-1]
        self._content.setPlainText(text)

    def _update_height(self) -> None:
        """Update height based on content."""
        doc = self._content.document()
        doc.setTextWidth(600)
        height = int(doc.size().height()) + 8
        self._content.setFixedHeight(min(height, 600))


class SimpleChatView(QWidget):
    """Simple text-based chat view - VSCode extension style."""

    def __init__(self, parent: QWidget | None = None) -> None:
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
