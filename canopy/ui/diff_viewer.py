"""Diff viewer widget for VSCode-style diff display."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class DiffHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for diff content."""

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

    def highlightBlock(self, text: str) -> None:
        """Highlight a block of text."""
        if text.startswith("+") and not text.startswith("+++"):
            self.setFormat(0, len(text), self._add_format)
        elif text.startswith("-") and not text.startswith("---"):
            self.setFormat(0, len(text), self._del_format)
        elif text.startswith("@@"):
            self.setFormat(0, len(text), self._hunk_format)


class DiffTextEdit(QTextEdit):
    """Text edit optimized for diff display."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Monospace font
        font = QFont("JetBrains Mono", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        # No frame
        self.setFrameStyle(QFrame.Shape.NoFrame)

        # Apply highlighter
        self._highlighter = DiffHighlighter(self.document())


class FileListItem(QListWidgetItem):
    """List item representing a changed file."""

    def __init__(self, file_info: dict) -> None:
        super().__init__()
        self.file_info = file_info
        self._setup_display()

    def _setup_display(self) -> None:
        """Set up the display text and icon."""
        path = self.file_info["path"]
        status = self.file_info["status"]
        additions = self.file_info.get("additions", 0)
        deletions = self.file_info.get("deletions", 0)

        # Status indicator
        status_icons = {
            "modified": "M",
            "added": "A",
            "deleted": "D",
            "renamed": "R",
            "copied": "C",
        }
        icon = status_icons.get(status, "?")

        # Display text
        self.setText(f"{icon}  {path}  +{additions} -{deletions}")

        # Color based on status
        colors = {
            "modified": QColor("#facc15"),  # Yellow
            "added": QColor("#4ade80"),  # Green
            "deleted": QColor("#f87171"),  # Red
            "renamed": QColor("#60a5fa"),  # Blue
        }
        if status in colors:
            self.setForeground(colors[status])


class DiffViewer(QWidget):
    """VSCode-style diff viewer widget."""

    file_selected = Signal(str)  # Emits file path when selected
    apply_requested = Signal(str)  # Request to apply changes to file
    discard_requested = Signal(str)  # Request to discard changes to file
    stage_requested = Signal(str)  # Request to stage file
    unstage_requested = Signal(str)  # Request to unstage file

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_file: Optional[str] = None
        self._worktree_path: Optional[Path] = None
        self._files: list[dict] = []
        self._staged: bool = False
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

        self._title_label = QLabel("Changes")
        self._title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        # Toggle staged/unstaged
        self._staged_btn = QPushButton("Staged")
        self._staged_btn.setCheckable(True)
        self._staged_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #4a4a4a;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #d97706;
                border-color: #d97706;
            }
            QPushButton:hover {
                border-color: #6a6a6a;
            }
        """)
        self._staged_btn.clicked.connect(self._on_staged_toggled)
        header_layout.addWidget(self._staged_btn)

        # Refresh button
        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setFixedSize(28, 28)
        self._refresh_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        self._refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(self._refresh_btn)

        layout.addWidget(header)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # File list (left)
        file_list_container = QWidget()
        file_list_layout = QVBoxLayout(file_list_container)
        file_list_layout.setContentsMargins(0, 0, 0, 0)
        file_list_layout.setSpacing(0)

        self._file_list = QListWidget()
        self._file_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: none;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 6px 12px;
                border-bottom: 1px solid #2a2a2a;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
            QListWidget::item:hover {
                background-color: #2a2a2a;
            }
        """)
        self._file_list.currentItemChanged.connect(self._on_file_selected)
        file_list_layout.addWidget(self._file_list)

        splitter.addWidget(file_list_container)

        # Diff view (right)
        diff_container = QWidget()
        diff_layout = QVBoxLayout(diff_container)
        diff_layout.setContentsMargins(0, 0, 0, 0)
        diff_layout.setSpacing(0)

        # File actions bar
        actions_bar = QWidget()
        actions_bar.setStyleSheet("background-color: #252525;")
        actions_layout = QHBoxLayout(actions_bar)
        actions_layout.setContentsMargins(8, 4, 8, 4)

        self._file_label = QLabel("No file selected")
        self._file_label.setStyleSheet("font-size: 11px; color: #9ca3af;")
        actions_layout.addWidget(self._file_label)

        actions_layout.addStretch()

        # Stage/Unstage button
        self._stage_btn = QPushButton("Stage")
        self._stage_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                border: none;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
                color: white;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
            QPushButton:disabled {
                background-color: #4a4a4a;
            }
        """)
        self._stage_btn.clicked.connect(self._on_stage_clicked)
        self._stage_btn.setEnabled(False)
        actions_layout.addWidget(self._stage_btn)

        # Discard button
        self._discard_btn = QPushButton("Discard")
        self._discard_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                border: none;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
                color: white;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #4a4a4a;
            }
        """)
        self._discard_btn.clicked.connect(self._on_discard_clicked)
        self._discard_btn.setEnabled(False)
        actions_layout.addWidget(self._discard_btn)

        diff_layout.addWidget(actions_bar)

        # Diff text
        self._diff_text = DiffTextEdit()
        self._diff_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
        """)
        diff_layout.addWidget(self._diff_text)

        splitter.addWidget(diff_container)
        splitter.setSizes([250, 550])

        layout.addWidget(splitter)

    def set_worktree(self, worktree_path: Path) -> None:
        """Set the worktree to show diffs for."""
        self._worktree_path = worktree_path
        self.refresh()

    def set_files(self, files: list[dict]) -> None:
        """Set the list of changed files."""
        self._files = files
        self._file_list.clear()

        for file_info in files:
            item = FileListItem(file_info)
            self._file_list.addItem(item)

        # Update title
        total = len(files)
        self._title_label.setText(f"Changes ({total})")

    def set_diff(self, file_path: str, diff_data: dict) -> None:
        """Set the diff content for a file."""
        self._current_file = file_path
        self._file_label.setText(file_path)

        # Display raw diff
        raw_diff = diff_data.get("raw", "")
        self._diff_text.setPlainText(raw_diff)

        # Enable action buttons
        self._stage_btn.setEnabled(True)
        self._discard_btn.setEnabled(not self._staged)

        # Update stage button text
        if self._staged:
            self._stage_btn.setText("Unstage")
        else:
            self._stage_btn.setText("Stage")

    def clear(self) -> None:
        """Clear the diff viewer."""
        self._file_list.clear()
        self._diff_text.clear()
        self._current_file = None
        self._file_label.setText("No file selected")
        self._stage_btn.setEnabled(False)
        self._discard_btn.setEnabled(False)
        self._title_label.setText("Changes")

    def refresh(self) -> None:
        """Refresh the diff view (emit signal to parent)."""
        # This will be connected to the session manager
        pass

    def _on_staged_toggled(self, checked: bool) -> None:
        """Handle staged toggle."""
        self._staged = checked
        self.refresh()

    def _on_file_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """Handle file selection."""
        if isinstance(current, FileListItem):
            self.file_selected.emit(current.file_info["path"])

    def _on_stage_clicked(self) -> None:
        """Handle stage/unstage button click."""
        if self._current_file:
            if self._staged:
                self.unstage_requested.emit(self._current_file)
            else:
                self.stage_requested.emit(self._current_file)

    def _on_discard_clicked(self) -> None:
        """Handle discard button click."""
        if self._current_file:
            self.discard_requested.emit(self._current_file)

    @property
    def is_staged_view(self) -> bool:
        """Check if viewing staged changes."""
        return self._staged


class InlineDiffViewer(QWidget):
    """Inline diff viewer showing old and new content side by side."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        # Old content (left)
        old_container = QWidget()
        old_layout = QVBoxLayout(old_container)
        old_layout.setContentsMargins(0, 0, 0, 0)
        old_layout.setSpacing(0)

        old_header = QLabel("Original")
        old_header.setStyleSheet("""
            background-color: #3f1d1d;
            color: #f87171;
            padding: 4px 8px;
            font-size: 11px;
        """)
        old_layout.addWidget(old_header)

        self._old_text = QTextEdit()
        self._old_text.setReadOnly(True)
        self._old_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
            }
        """)
        font = QFont("JetBrains Mono", 11)
        self._old_text.setFont(font)
        old_layout.addWidget(self._old_text)

        layout.addWidget(old_container)

        # New content (right)
        new_container = QWidget()
        new_layout = QVBoxLayout(new_container)
        new_layout.setContentsMargins(0, 0, 0, 0)
        new_layout.setSpacing(0)

        new_header = QLabel("Modified")
        new_header.setStyleSheet("""
            background-color: #1e3a29;
            color: #4ade80;
            padding: 4px 8px;
            font-size: 11px;
        """)
        new_layout.addWidget(new_header)

        self._new_text = QTextEdit()
        self._new_text.setReadOnly(True)
        self._new_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
            }
        """)
        self._new_text.setFont(font)
        new_layout.addWidget(self._new_text)

        layout.addWidget(new_container)

        # Sync scrolling
        self._old_text.verticalScrollBar().valueChanged.connect(
            self._new_text.verticalScrollBar().setValue
        )
        self._new_text.verticalScrollBar().valueChanged.connect(
            self._old_text.verticalScrollBar().setValue
        )

    def set_content(self, old_content: str, new_content: str) -> None:
        """Set the old and new content."""
        self._old_text.setPlainText(old_content)
        self._new_text.setPlainText(new_content)

    def clear(self) -> None:
        """Clear the viewer."""
        self._old_text.clear()
        self._new_text.clear()
