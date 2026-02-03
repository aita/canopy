# Canopy

Git Worktree IDE with Claude Code integration.

Canopy は Git worktree と Claude Code CLI を統合管理する PyQt デスクトップアプリケーションです。ブランチごとに独立した作業環境（worktree）を作成し、各 worktree に対して複数の Claude Code セッションを管理できます。

## Features

- **Worktree 管理**
  - リポジトリの登録・管理
  - ブランチ一覧表示（ローカル/リモート）
  - Worktree の作成（既存ブランチ / 新規ブランチ）
  - Worktree の削除

- **セッション管理**
  - Worktree ごとに複数の Claude Code セッションを作成
  - セッションの切り替え・終了
  - セッション履歴の永続化

- **チャット機能**
  - Claude Code CLI とのインタラクティブ通信
  - メッセージ送信・応答表示
  - セッション継続（`--resume`）対応

## Requirements

- Python 3.11+
- Git
- [Claude Code CLI](https://github.com/anthropics/claude-code)

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/aita/canopy.git
cd canopy

# Install dependencies and run
uv sync
uv run canopy
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/aita/canopy.git
cd canopy

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or .venv\Scripts\activate  # Windows

# Install
pip install -e .

# Run
canopy
```

## Usage

### Starting the Application

```bash
# With uv
uv run canopy

# Or if installed via pip
canopy
```

### Basic Workflow

1. **リポジトリを追加**: `File > Add Repository...` または `+ Repository` ボタン
2. **Worktree を作成**: リポジトリを選択して `+ Worktree` ボタン
3. **セッションを開始**: Worktree をダブルクリック、または右クリックで `New Session`
4. **Claude と会話**: メッセージを入力して Enter で送信

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Add Repository |
| `Ctrl+N` | New Session |
| `Ctrl+W` | Close Session |
| `Ctrl+B` | Toggle Sidebar |
| `Ctrl+Q` | Quit |
| `Enter` | Send Message |
| `Shift+Enter` | New Line in Message |

## Project Structure

```
canopy/
├── main.py                 # Entry point
├── core/
│   ├── git_service.py      # Git/Worktree operations
│   ├── session_manager.py  # Session lifecycle management
│   └── claude_runner.py    # Claude Code CLI integration
├── models/
│   ├── repository.py       # Repository, Worktree models
│   ├── session.py          # Session, Message models
│   └── config.py           # Application configuration
├── ui/
│   ├── main_window.py      # Main application window
│   ├── worktree_panel.py   # Left sidebar tree view
│   ├── session_tabs.py     # Session tab management
│   ├── chat_view.py        # Chat message display
│   ├── message_input.py    # Message input widget
│   └── dialogs/            # Dialog windows
└── resources/
    └── styles.qss          # Qt stylesheet
```

## Configuration

設定ファイルは `~/.config/canopy/` に保存されます:

- `config.json` - アプリケーション設定
- `sessions/sessions.json` - セッション履歴

## Development

```bash
# Install with dev dependencies
uv sync --dev

# Run linter
uv run ruff check .

# Run type checker
uv run mypy canopy/

# Run tests
uv run pytest
```

## License

MIT License
