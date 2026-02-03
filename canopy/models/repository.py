"""Repository and Worktree data models."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Worktree:
    """Represents a Git worktree."""

    path: Path
    branch: str
    commit: str
    is_main: bool = False
    is_bare: bool = False
    is_detached: bool = False

    @property
    def name(self) -> str:
        """Return display name for the worktree."""
        if self.is_main:
            return f"{self.branch} (main)"
        return self.branch

    @property
    def short_commit(self) -> str:
        """Return shortened commit hash."""
        return self.commit[:7] if self.commit else ""

    def __hash__(self) -> int:
        return hash(str(self.path))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Worktree):
            return False
        return self.path == other.path


@dataclass
class Repository:
    """Represents a Git repository."""

    path: Path
    worktrees: list[Worktree] = field(default_factory=list)

    @property
    def name(self) -> str:
        """Return display name for the repository."""
        return self.path.name

    @property
    def main_worktree(self) -> "Worktree | None":
        """Return the main worktree if exists."""
        for wt in self.worktrees:
            if wt.is_main:
                return wt
        return None

    def get_worktree_by_branch(self, branch: str) -> "Worktree | None":
        """Find worktree by branch name."""
        for wt in self.worktrees:
            if wt.branch == branch:
                return wt
        return None

    def get_worktree_by_path(self, path: Path) -> "Worktree | None":
        """Find worktree by path."""
        for wt in self.worktrees:
            if wt.path == path:
                return wt
        return None

    def __hash__(self) -> int:
        return hash(str(self.path))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Repository):
            return False
        return self.path == other.path
