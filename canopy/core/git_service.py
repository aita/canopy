"""Git service for worktree and branch operations."""

import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from canopy.models.repository import Repository, Worktree


class GitError(Exception):
    """Exception raised for Git operation errors."""

    pass


class GitService(QObject):
    """Service for Git operations including worktree management."""

    # Signals
    worktrees_changed = Signal(Repository)
    error_occurred = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

    def _run_git(
        self, args: list[str], cwd: Optional[Path] = None, check: bool = True
    ) -> subprocess.CompletedProcess:
        """Run a git command and return the result."""
        cmd = ["git"] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            raise GitError(f"Git command failed: {error_msg}")
        except FileNotFoundError:
            raise GitError("Git is not installed or not in PATH")

    def is_git_repository(self, path: Path) -> bool:
        """Check if a path is a Git repository."""
        try:
            result = self._run_git(
                ["rev-parse", "--git-dir"], cwd=path, check=False
            )
            return result.returncode == 0
        except GitError:
            return False

    def get_repository(self, path: Path) -> Repository:
        """Get repository information including worktrees."""
        if not self.is_git_repository(path):
            raise GitError(f"Not a Git repository: {path}")

        repo = Repository(path=path.resolve())
        repo.worktrees = self.list_worktrees(path)
        return repo

    def list_worktrees(self, repo_path: Path) -> list[Worktree]:
        """List all worktrees for a repository."""
        result = self._run_git(
            ["worktree", "list", "--porcelain"], cwd=repo_path
        )

        worktrees = []
        current_worktree: dict = {}

        for line in result.stdout.strip().split("\n"):
            if not line:
                if current_worktree:
                    worktrees.append(self._parse_worktree(current_worktree))
                    current_worktree = {}
                continue

            if line.startswith("worktree "):
                current_worktree["path"] = line[9:]
            elif line.startswith("HEAD "):
                current_worktree["commit"] = line[5:]
            elif line.startswith("branch "):
                # refs/heads/branch-name -> branch-name
                branch_ref = line[7:]
                if branch_ref.startswith("refs/heads/"):
                    current_worktree["branch"] = branch_ref[11:]
                else:
                    current_worktree["branch"] = branch_ref
            elif line == "bare":
                current_worktree["bare"] = True
            elif line == "detached":
                current_worktree["detached"] = True

        # Don't forget the last worktree
        if current_worktree:
            worktrees.append(self._parse_worktree(current_worktree))

        # Mark the first one as main (it's the original repo)
        if worktrees:
            worktrees[0].is_main = True

        return worktrees

    def _parse_worktree(self, data: dict) -> Worktree:
        """Parse worktree data into a Worktree object."""
        return Worktree(
            path=Path(data.get("path", "")),
            branch=data.get("branch", ""),
            commit=data.get("commit", ""),
            is_bare=data.get("bare", False),
            is_detached=data.get("detached", False),
        )

    def list_branches(
        self, repo_path: Path, include_remote: bool = True
    ) -> tuple[list[str], list[str]]:
        """List local and remote branches.

        Returns:
            Tuple of (local_branches, remote_branches)
        """
        # Local branches
        result = self._run_git(
            ["branch", "--format=%(refname:short)"], cwd=repo_path
        )
        local_branches = [
            b.strip() for b in result.stdout.strip().split("\n") if b.strip()
        ]

        remote_branches = []
        if include_remote:
            result = self._run_git(
                ["branch", "-r", "--format=%(refname:short)"], cwd=repo_path
            )
            remote_branches = [
                b.strip()
                for b in result.stdout.strip().split("\n")
                if b.strip() and not b.strip().endswith("/HEAD")
            ]

        return local_branches, remote_branches

    def get_current_branch(self, repo_path: Path) -> str:
        """Get the current branch name."""
        result = self._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path
        )
        return result.stdout.strip()

    def create_worktree(
        self,
        repo_path: Path,
        worktree_path: Path,
        branch: str,
        create_branch: bool = False,
        base_branch: Optional[str] = None,
    ) -> Worktree:
        """Create a new worktree.

        Args:
            repo_path: Path to the main repository
            worktree_path: Path where the worktree will be created
            branch: Branch name for the worktree
            create_branch: If True, create a new branch
            base_branch: Base branch for new branch (if create_branch is True)

        Returns:
            The created Worktree object
        """
        args = ["worktree", "add"]

        if create_branch:
            args.extend(["-b", branch])
            args.append(str(worktree_path))
            if base_branch:
                args.append(base_branch)
        else:
            args.append(str(worktree_path))
            args.append(branch)

        self._run_git(args, cwd=repo_path)

        # Get the created worktree info
        worktrees = self.list_worktrees(repo_path)
        for wt in worktrees:
            if wt.path == worktree_path.resolve():
                return wt

        raise GitError("Worktree was created but not found in list")

    def remove_worktree(
        self, repo_path: Path, worktree_path: Path, force: bool = False
    ) -> None:
        """Remove a worktree.

        Args:
            repo_path: Path to the main repository
            worktree_path: Path to the worktree to remove
            force: If True, force removal even with uncommitted changes
        """
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(worktree_path))

        self._run_git(args, cwd=repo_path)

    def prune_worktrees(self, repo_path: Path) -> None:
        """Prune stale worktree references."""
        self._run_git(["worktree", "prune"], cwd=repo_path)

    def fetch(
        self, repo_path: Path, remote: str = "origin", prune: bool = True
    ) -> None:
        """Fetch from remote."""
        args = ["fetch", remote]
        if prune:
            args.append("--prune")
        self._run_git(args, cwd=repo_path)

    def get_worktree_status(self, worktree_path: Path) -> dict:
        """Get status of a worktree (modified files, etc.)."""
        result = self._run_git(
            ["status", "--porcelain"], cwd=worktree_path
        )

        status = {
            "modified": [],
            "added": [],
            "deleted": [],
            "untracked": [],
        }

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            code = line[:2]
            filename = line[3:]

            if code[0] == "M" or code[1] == "M":
                status["modified"].append(filename)
            elif code[0] == "A":
                status["added"].append(filename)
            elif code[0] == "D" or code[1] == "D":
                status["deleted"].append(filename)
            elif code == "??":
                status["untracked"].append(filename)

        return status

    def get_default_worktree_path(self, repo_path: Path, branch: str) -> Path:
        """Generate a default worktree path for a branch."""
        # Put worktrees in a sibling directory to the main repo
        safe_branch = branch.replace("/", "-")
        parent = repo_path.parent
        return parent / f"{repo_path.name}-{safe_branch}"

    def get_diff(
        self,
        worktree_path: Path,
        staged: bool = False,
        file_path: Optional[str] = None,
    ) -> str:
        """Get the diff for a worktree.

        Args:
            worktree_path: Path to the worktree
            staged: If True, show staged changes; otherwise show unstaged
            file_path: Optional specific file to diff

        Returns:
            The diff output as string
        """
        args = ["diff"]
        if staged:
            args.append("--staged")
        args.extend(["--color=never"])
        if file_path:
            args.extend(["--", file_path])

        result = self._run_git(args, cwd=worktree_path)
        return result.stdout

    def get_diff_stat(self, worktree_path: Path, staged: bool = False) -> str:
        """Get diff statistics (summary) for a worktree.

        Args:
            worktree_path: Path to the worktree
            staged: If True, show staged changes; otherwise show unstaged

        Returns:
            The diff stat output
        """
        args = ["diff", "--stat"]
        if staged:
            args.append("--staged")

        result = self._run_git(args, cwd=worktree_path)
        return result.stdout

    def get_file_diff(
        self,
        worktree_path: Path,
        file_path: str,
        staged: bool = False,
    ) -> dict:
        """Get detailed diff for a specific file.

        Args:
            worktree_path: Path to the worktree
            file_path: Path to the file (relative to worktree)
            staged: If True, show staged changes

        Returns:
            Dictionary with diff info: hunks, additions, deletions
        """
        args = ["diff", "-U3"]  # 3 lines of context
        if staged:
            args.append("--staged")
        args.extend(["--", file_path])

        result = self._run_git(args, cwd=worktree_path)
        diff_text = result.stdout

        return self._parse_diff(diff_text)

    def _parse_diff(self, diff_text: str) -> dict:
        """Parse a unified diff into structured data."""
        hunks = []
        current_hunk = None
        additions = 0
        deletions = 0
        old_file = ""
        new_file = ""

        lines = diff_text.split("\n")
        for line in lines:
            if line.startswith("--- "):
                old_file = line[4:]
            elif line.startswith("+++ "):
                new_file = line[4:]
            elif line.startswith("@@"):
                # Parse hunk header: @@ -start,count +start,count @@
                if current_hunk:
                    hunks.append(current_hunk)
                current_hunk = {
                    "header": line,
                    "lines": [],
                    "old_start": 0,
                    "new_start": 0,
                }
                # Extract line numbers
                import re
                match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if match:
                    current_hunk["old_start"] = int(match.group(1))
                    current_hunk["new_start"] = int(match.group(2))
            elif current_hunk is not None:
                if line.startswith("+") and not line.startswith("+++"):
                    current_hunk["lines"].append({"type": "add", "content": line[1:]})
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    current_hunk["lines"].append({"type": "del", "content": line[1:]})
                    deletions += 1
                elif line.startswith(" "):
                    current_hunk["lines"].append({"type": "context", "content": line[1:]})
                elif line == "":
                    current_hunk["lines"].append({"type": "context", "content": ""})

        if current_hunk:
            hunks.append(current_hunk)

        return {
            "old_file": old_file,
            "new_file": new_file,
            "hunks": hunks,
            "additions": additions,
            "deletions": deletions,
            "raw": diff_text,
        }

    def get_changed_files(
        self,
        worktree_path: Path,
        staged: bool = False,
    ) -> list[dict]:
        """Get list of changed files with their status.

        Args:
            worktree_path: Path to the worktree
            staged: If True, show only staged changes

        Returns:
            List of dicts with file info: path, status, additions, deletions
        """
        # Get file list with status
        args = ["diff", "--name-status"]
        if staged:
            args.append("--staged")

        result = self._run_git(args, cwd=worktree_path)
        files = []

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                status_code = parts[0]
                file_path = parts[1]
                status = {
                    "M": "modified",
                    "A": "added",
                    "D": "deleted",
                    "R": "renamed",
                    "C": "copied",
                }.get(status_code[0], "unknown")

                files.append({
                    "path": file_path,
                    "status": status,
                    "status_code": status_code,
                })

        # Get stats for each file
        args = ["diff", "--numstat"]
        if staged:
            args.append("--staged")

        result = self._run_git(args, cwd=worktree_path)
        stats = {}
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                add = int(parts[0]) if parts[0] != "-" else 0
                delete = int(parts[1]) if parts[1] != "-" else 0
                path = parts[2]
                stats[path] = {"additions": add, "deletions": delete}

        # Merge stats into files
        for f in files:
            if f["path"] in stats:
                f.update(stats[f["path"]])
            else:
                f["additions"] = 0
                f["deletions"] = 0

        return files

    def get_file_content(self, worktree_path: Path, file_path: str, ref: str = "HEAD") -> str:
        """Get file content at a specific ref.

        Args:
            worktree_path: Path to the worktree
            file_path: Path to the file (relative to worktree)
            ref: Git reference (HEAD, commit hash, etc.)

        Returns:
            File content as string
        """
        try:
            result = self._run_git(
                ["show", f"{ref}:{file_path}"],
                cwd=worktree_path,
            )
            return result.stdout
        except GitError:
            return ""  # File doesn't exist at this ref

    def stage_file(self, worktree_path: Path, file_path: str) -> None:
        """Stage a file for commit."""
        self._run_git(["add", file_path], cwd=worktree_path)

    def unstage_file(self, worktree_path: Path, file_path: str) -> None:
        """Unstage a file."""
        self._run_git(["reset", "HEAD", file_path], cwd=worktree_path)

    def discard_changes(self, worktree_path: Path, file_path: str) -> None:
        """Discard changes to a file (restore from HEAD)."""
        self._run_git(["checkout", "--", file_path], cwd=worktree_path)

    def create_stash(
        self,
        worktree_path: Path,
        message: Optional[str] = None,
        include_untracked: bool = False,
    ) -> str:
        """Create a stash.

        Returns:
            Stash reference (e.g., stash@{0})
        """
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])
        if include_untracked:
            args.append("-u")

        self._run_git(args, cwd=worktree_path)

        # Get the stash ref
        result = self._run_git(["stash", "list", "-1"], cwd=worktree_path)
        if result.stdout.strip():
            return result.stdout.strip().split(":")[0]
        return "stash@{0}"

    def apply_stash(
        self,
        worktree_path: Path,
        stash_ref: str = "stash@{0}",
        pop: bool = False,
    ) -> None:
        """Apply a stash.

        Args:
            worktree_path: Path to the worktree
            stash_ref: Stash reference to apply
            pop: If True, also drop the stash after applying
        """
        cmd = "pop" if pop else "apply"
        self._run_git(["stash", cmd, stash_ref], cwd=worktree_path)

    def list_stashes(self, worktree_path: Path) -> list[dict]:
        """List all stashes.

        Returns:
            List of stash info dicts
        """
        result = self._run_git(["stash", "list"], cwd=worktree_path)
        stashes = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            # Format: stash@{0}: WIP on branch: message
            parts = line.split(": ", 2)
            if len(parts) >= 2:
                stashes.append({
                    "ref": parts[0],
                    "branch": parts[1].replace("WIP on ", "").replace("On ", ""),
                    "message": parts[2] if len(parts) > 2 else "",
                })
        return stashes
