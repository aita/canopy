# Canopy

A desktop application for managing Git worktrees with Claude Code integration.

## Features

- **Worktree Management**: Create, switch, and delete Git worktrees per branch
- **Session Management**: Run multiple Claude Code sessions per worktree
- **Chat Interface**: Interactive communication with Claude Code CLI

## Requirements

- Python 3.11+
- Git
- [Claude Code CLI](https://github.com/anthropics/claude-code)

## Installation

```bash
git clone https://github.com/aita/canopy.git
cd canopy
uv sync
uv run canopy
```

## Usage

1. Add a repository via `File > Add Repository...`
2. Create a worktree from a branch
3. Start a Claude Code session in the worktree
4. Chat with Claude

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Add Repository |
| `Ctrl+N` | New Session |
| `Ctrl+W` | Close Session |
| `Ctrl+B` | Toggle Sidebar |
| `Ctrl+Q` | Quit |

## Development

```bash
uv sync --dev
uv run ruff check .
uv run mypy canopy/
uv run pytest
```

## License

MIT License
