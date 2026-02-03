"""Command log panel for displaying tool executions."""

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
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


class ToolExecutionWidget(QFrame):
    """Widget displaying a single tool execution."""

    def __init__(
        self,
        tool_name: str,
        tool_input: dict,
        result: str | None = None,
        status: str = "pending",
        timestamp: datetime | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tool_name = tool_name
        self._tool_input = tool_input
        self._result = result
        self._status = status
        self._timestamp = timestamp or datetime.now()
        self._expanded = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            ToolExecutionWidget {
                background-color: #252525;
                border-radius: 4px;
                margin: 2px 0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Header row
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        # Status indicator
        self._status_indicator = QLabel()
        self._status_indicator.setFixedSize(8, 8)
        self._update_status_indicator()
        header_layout.addWidget(self._status_indicator)

        # Tool name
        name_label = QLabel(self._get_tool_display_name())
        name_label.setStyleSheet("""
            font-weight: bold;
            font-size: 11px;
            color: #60a5fa;
        """)
        header_layout.addWidget(name_label)

        # Brief info
        brief = self._get_brief_info()
        if brief:
            brief_label = QLabel(brief)
            brief_label.setStyleSheet("font-size: 11px; color: #9ca3af;")
            brief_label.setMaximumWidth(300)
            header_layout.addWidget(brief_label)

        header_layout.addStretch()

        # Timestamp
        time_label = QLabel(self._timestamp.strftime("%H:%M:%S"))
        time_label.setStyleSheet("font-size: 10px; color: #6b7280;")
        header_layout.addWidget(time_label)

        # Expand/collapse button
        self._expand_btn = QPushButton("▶")
        self._expand_btn.setFixedSize(20, 20)
        self._expand_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #9ca3af;
                font-size: 10px;
            }
            QPushButton:hover {
                color: white;
            }
        """)
        self._expand_btn.clicked.connect(self._toggle_expand)
        header_layout.addWidget(self._expand_btn)

        layout.addWidget(header)

        # Details (hidden by default)
        self._details = QWidget()
        self._details.setVisible(False)
        details_layout = QVBoxLayout(self._details)
        details_layout.setContentsMargins(16, 4, 0, 0)
        details_layout.setSpacing(4)

        # Input
        if self._tool_input:
            input_label = QLabel("Input:")
            input_label.setStyleSheet("font-size: 10px; color: #9ca3af;")
            details_layout.addWidget(input_label)

            input_text = QTextEdit()
            input_text.setReadOnly(True)
            input_text.setPlainText(self._format_input())
            input_text.setMaximumHeight(100)
            input_text.setStyleSheet("""
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: 1px solid #3a3a3a;
                    border-radius: 2px;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 10px;
                }
            """)
            details_layout.addWidget(input_text)

        # Result
        if self._result:
            result_label = QLabel("Result:")
            result_label.setStyleSheet("font-size: 10px; color: #9ca3af;")
            details_layout.addWidget(result_label)

            result_text = QTextEdit()
            result_text.setReadOnly(True)
            result_text.setPlainText(self._result[:2000])  # Limit length
            result_text.setMaximumHeight(150)
            result_text.setStyleSheet("""
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: 1px solid #3a3a3a;
                    border-radius: 2px;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 10px;
                }
            """)
            details_layout.addWidget(result_text)

        layout.addWidget(self._details)

    def _get_tool_display_name(self) -> str:
        """Get display name for the tool."""
        display_names = {
            "Read": "📄 Read File",
            "Write": "✏️ Write File",
            "Edit": "🔧 Edit File",
            "Bash": "💻 Run Command",
            "Glob": "🔍 Search Files",
            "Grep": "🔎 Search Content",
            "Task": "📋 Task",
            "WebFetch": "🌐 Web Fetch",
            "TodoWrite": "📝 Update Todos",
        }
        return display_names.get(self._tool_name, f"🔧 {self._tool_name}")

    def _get_brief_info(self) -> str:
        """Get brief info about the tool execution."""
        if not self._tool_input:
            return ""

        if self._tool_name == "Read":
            return self._tool_input.get("file_path", "")
        elif self._tool_name in ("Write", "Edit"):
            return self._tool_input.get("file_path", "")
        elif self._tool_name == "Bash":
            cmd = self._tool_input.get("command", "")
            return cmd[:50] + "..." if len(cmd) > 50 else cmd
        elif self._tool_name == "Glob":
            return self._tool_input.get("pattern", "")
        elif self._tool_name == "Grep":
            return self._tool_input.get("pattern", "")
        return ""

    def _format_input(self) -> str:
        """Format the tool input for display."""
        import json
        try:
            return json.dumps(self._tool_input, indent=2, ensure_ascii=False)
        except Exception:
            return str(self._tool_input)

    def _update_status_indicator(self) -> None:
        """Update the status indicator color."""
        colors = {
            "pending": "#facc15",  # Yellow
            "running": "#60a5fa",  # Blue
            "success": "#4ade80",  # Green
            "error": "#f87171",  # Red
        }
        color = colors.get(self._status, "#6b7280")
        self._status_indicator.setStyleSheet(f"""
            background-color: {color};
            border-radius: 4px;
        """)

    def _toggle_expand(self) -> None:
        """Toggle the expanded state."""
        self._expanded = not self._expanded
        self._details.setVisible(self._expanded)
        self._expand_btn.setText("▼" if self._expanded else "▶")

    def set_result(self, result: str, status: str = "success") -> None:
        """Set the result of the tool execution."""
        self._result = result
        self._status = status
        self._update_status_indicator()
        # Rebuild details if expanded
        if self._expanded:
            self._toggle_expand()
            self._toggle_expand()


class CommandLogPanel(QWidget):
    """Panel for displaying Claude's tool executions."""

    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._executions: list[ToolExecutionWidget] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("""
            background-color: #1e1e1e;
            border-bottom: 1px solid #3a3a3a;
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Tool Executions")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #4a4a4a;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                border-color: #6a6a6a;
            }
        """)
        clear_btn.clicked.connect(self._on_clear)
        header_layout.addWidget(clear_btn)

        layout.addWidget(header)

        # Scroll area for executions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
            }
        """)

        # Container for execution widgets
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(8, 8, 8, 8)
        self._container_layout.setSpacing(4)
        self._container_layout.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def add_tool_use(
        self,
        tool_name: str,
        tool_input: dict,
    ) -> ToolExecutionWidget:
        """Add a tool execution to the log.

        Returns the widget so the result can be set later.
        """
        widget = ToolExecutionWidget(
            tool_name=tool_name,
            tool_input=tool_input,
            status="running",
        )

        # Insert before the stretch
        self._container_layout.insertWidget(
            self._container_layout.count() - 1, widget
        )
        self._executions.append(widget)

        return widget

    def add_tool_result(
        self,
        tool_name: str,
        result: str,
    ) -> None:
        """Add a result to the most recent matching tool execution."""
        # Find the most recent execution with this tool name
        for widget in reversed(self._executions):
            if widget._tool_name == tool_name and widget._status == "running":
                widget.set_result(result, "success")
                break

    def clear(self) -> None:
        """Clear all executions."""
        for widget in self._executions:
            widget.deleteLater()
        self._executions.clear()

        # Remove all widgets except the stretch
        while self._container_layout.count() > 1:
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_clear(self) -> None:
        """Handle clear button click."""
        self.clear()
        self.clear_requested.emit()
