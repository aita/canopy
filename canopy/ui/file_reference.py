"""File reference panel for selecting files to add to prompts."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class FileReferenceItem(QListWidgetItem):
    """List item representing a referenced file."""

    def __init__(
        self,
        file_path: Path,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> None:
        super().__init__()
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self._setup_display()

    def _setup_display(self) -> None:
        """Set up the display."""
        name = self.file_path.name
        if self.start_line is not None:
            if self.end_line is not None and self.end_line != self.start_line:
                line_info = f":{self.start_line}-{self.end_line}"
            else:
                line_info = f":{self.start_line}"
        else:
            line_info = ""

        self.setText(f"📄 {name}{line_info}")
        self.setToolTip(str(self.file_path))

    def to_reference(self) -> str:
        """Convert to a reference string for the prompt."""
        ref = str(self.file_path)
        if self.start_line is not None:
            if self.end_line is not None and self.end_line != self.start_line:
                ref += f":{self.start_line}-{self.end_line}"
            else:
                ref += f":{self.start_line}"
        return ref


class FileReferencePanel(QWidget):
    """Panel for selecting and managing file references."""

    files_changed = Signal(list)  # Emits list of file references

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worktree_path: Path | None = None
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

        title = QLabel("File References")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Add file button
        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #d97706;
                border: none;
                border-radius: 3px;
                font-size: 14px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background-color: #b45309;
            }
        """)
        add_btn.clicked.connect(self._on_add_file)
        header_layout.addWidget(add_btn)

        layout.addWidget(header)

        # Quick filter
        filter_container = QWidget()
        filter_container.setStyleSheet("background-color: #252525;")
        filter_layout = QHBoxLayout(filter_container)
        filter_layout.setContentsMargins(8, 6, 8, 6)

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter files...")
        self._filter_edit.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #d97706;
            }
        """)
        self._filter_edit.textChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._filter_edit)

        layout.addWidget(filter_container)

        # File list
        self._file_list = QListWidget()
        self._file_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: none;
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
        self._file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._file_list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._file_list)

        # Actions bar
        actions_bar = QWidget()
        actions_bar.setStyleSheet("background-color: #252525;")
        actions_layout = QHBoxLayout(actions_bar)
        actions_layout.setContentsMargins(8, 6, 8, 6)

        # Clear button
        clear_btn = QPushButton("Clear All")
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
        actions_layout.addWidget(clear_btn)

        actions_layout.addStretch()

        # Remove selected button
        remove_btn = QPushButton("Remove")
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
                color: white;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        remove_btn.clicked.connect(self._on_remove_selected)
        actions_layout.addWidget(remove_btn)

        layout.addWidget(actions_bar)

    def set_worktree(self, worktree_path: Path) -> None:
        """Set the worktree path for file selection."""
        self._worktree_path = worktree_path

    def add_file(
        self,
        file_path: Path,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> None:
        """Add a file reference."""
        # Check if already added
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if isinstance(item, FileReferenceItem):
                if item.file_path == file_path:
                    # Update line range if different
                    if item.start_line != start_line or item.end_line != end_line:
                        item.start_line = start_line
                        item.end_line = end_line
                        item._setup_display()
                    return

        item = FileReferenceItem(file_path, start_line, end_line)
        self._file_list.addItem(item)
        self._emit_files_changed()

    def get_references(self) -> list[str]:
        """Get list of file reference strings."""
        refs = []
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if isinstance(item, FileReferenceItem):
                refs.append(item.to_reference())
        return refs

    def clear(self) -> None:
        """Clear all file references."""
        self._file_list.clear()
        self._emit_files_changed()

    def _on_add_file(self) -> None:
        """Handle add file button click."""
        start_dir = str(self._worktree_path) if self._worktree_path else ""

        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Files",
            start_dir,
            "All Files (*)",
        )

        for path in file_paths:
            self.add_file(Path(path))

    def _on_remove_selected(self) -> None:
        """Remove selected items."""
        for item in self._file_list.selectedItems():
            row = self._file_list.row(item)
            self._file_list.takeItem(row)
        self._emit_files_changed()

    def _on_clear(self) -> None:
        """Clear all items."""
        self.clear()

    def _on_filter_changed(self, text: str) -> None:
        """Handle filter text change."""
        text_lower = text.lower()
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if isinstance(item, FileReferenceItem):
                visible = text_lower in str(item.file_path).lower()
                item.setHidden(not visible)

    def _on_context_menu(self, pos) -> None:
        """Show context menu."""
        # TODO: Add context menu with options like "Open in editor"
        pass

    def _emit_files_changed(self) -> None:
        """Emit the files changed signal."""
        self.files_changed.emit(self.get_references())


class FileTreePanel(QWidget):
    """Panel showing the file tree of the worktree."""

    file_selected = Signal(Path)  # Emits path when file is selected
    file_added = Signal(Path)  # Emits path when file is added to references

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worktree_path: Path | None = None
        self._model = QStandardItemModel()
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

        title = QLabel("Explorer")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(24, 24)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        layout.addWidget(header)

        # Tree view
        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setHeaderHidden(True)
        self._tree.setStyleSheet("""
            QTreeView {
                background-color: #1e1e1e;
                border: none;
                font-size: 11px;
            }
            QTreeView::item {
                padding: 4px 8px;
            }
            QTreeView::item:selected {
                background-color: #094771;
            }
            QTreeView::item:hover {
                background-color: #2a2a2a;
            }
        """)
        self._tree.doubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._tree)

    def set_worktree(self, worktree_path: Path) -> None:
        """Set the worktree to display."""
        self._worktree_path = worktree_path
        self.refresh()

    def refresh(self) -> None:
        """Refresh the file tree."""
        self._model.clear()

        if not self._worktree_path or not self._worktree_path.exists():
            return

        root_item = self._model.invisibleRootItem()
        self._populate_tree(self._worktree_path, root_item)

    def _populate_tree(
        self,
        path: Path,
        parent_item: QStandardItem,
        max_depth: int = 3,
        current_depth: int = 0,
    ) -> None:
        """Populate the tree with files and directories."""
        if current_depth >= max_depth:
            return

        try:
            # Sort: directories first, then files
            entries = sorted(
                path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )

            for entry in entries:
                # Skip hidden files and common ignore patterns
                if entry.name.startswith("."):
                    continue
                if entry.name in ("node_modules", "__pycache__", ".git", "venv", ".venv"):
                    continue

                if entry.is_dir():
                    item = QStandardItem(f"📁 {entry.name}")
                    item.setData(str(entry), Qt.ItemDataRole.UserRole)
                    item.setEditable(False)
                    parent_item.appendRow(item)
                    self._populate_tree(entry, item, max_depth, current_depth + 1)
                else:
                    icon = self._get_file_icon(entry)
                    item = QStandardItem(f"{icon} {entry.name}")
                    item.setData(str(entry), Qt.ItemDataRole.UserRole)
                    item.setEditable(False)
                    parent_item.appendRow(item)

        except PermissionError:
            pass

    def _get_file_icon(self, path: Path) -> str:
        """Get an icon for a file based on extension."""
        ext = path.suffix.lower()
        icons = {
            ".py": "🐍",
            ".js": "📜",
            ".ts": "📘",
            ".jsx": "⚛️",
            ".tsx": "⚛️",
            ".json": "📋",
            ".yaml": "📋",
            ".yml": "📋",
            ".md": "📝",
            ".txt": "📄",
            ".html": "🌐",
            ".css": "🎨",
            ".scss": "🎨",
            ".sql": "🗃️",
            ".sh": "💻",
            ".bash": "💻",
            ".rs": "🦀",
            ".go": "🐹",
            ".java": "☕",
            ".c": "🔧",
            ".cpp": "🔧",
            ".h": "🔧",
        }
        return icons.get(ext, "📄")

    def _on_item_double_clicked(self, index) -> None:
        """Handle item double-click."""
        item = self._model.itemFromIndex(index)
        if item:
            path_str = item.data(Qt.ItemDataRole.UserRole)
            if path_str:
                path = Path(path_str)
                if path.is_file():
                    self.file_added.emit(path)
