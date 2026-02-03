"""Tests for GitService."""

import subprocess
from pathlib import Path

import pytest

from canopy.core.git_service import GitError, GitService


class TestGitServiceParseDiff:
    """Tests for GitService._parse_diff()."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    def test_parse_simple_diff(self, git_service: GitService) -> None:
        """Test parsing a simple diff with additions and deletions."""
        diff_text = """--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 line1
-line2
+line2_modified
+line3_new
 line4
"""
        result = git_service._parse_diff(diff_text)

        assert result["old_file"] == "a/file.py"
        assert result["new_file"] == "b/file.py"
        assert result["additions"] == 2
        assert result["deletions"] == 1
        assert len(result["hunks"]) == 1

        hunk = result["hunks"][0]
        assert hunk["old_start"] == 1
        assert hunk["new_start"] == 1
        assert len(hunk["lines"]) >= 5  # May include trailing empty line

    def test_parse_diff_multiple_hunks(self, git_service: GitService) -> None:
        """Test parsing diff with multiple hunks."""
        diff_text = """--- a/file.py
+++ b/file.py
@@ -1,2 +1,2 @@
-old line 1
+new line 1
 unchanged
@@ -10,2 +10,3 @@
 context
+added line
 more context
"""
        result = git_service._parse_diff(diff_text)

        assert len(result["hunks"]) == 2
        assert result["hunks"][0]["old_start"] == 1
        assert result["hunks"][1]["old_start"] == 10

    def test_parse_empty_diff(self, git_service: GitService) -> None:
        """Test parsing empty diff."""
        result = git_service._parse_diff("")

        assert result["additions"] == 0
        assert result["deletions"] == 0
        assert len(result["hunks"]) == 0
        assert result["raw"] == ""

    def test_parse_diff_line_types(self, git_service: GitService) -> None:
        """Test that line types are correctly identified."""
        diff_text = """--- a/test.txt
+++ b/test.txt
@@ -1,4 +1,4 @@
 context line
-deleted line
+added line
 another context
"""
        result = git_service._parse_diff(diff_text)
        lines = result["hunks"][0]["lines"]

        assert lines[0]["type"] == "context"
        assert lines[0]["content"] == "context line"
        assert lines[1]["type"] == "del"
        assert lines[1]["content"] == "deleted line"
        assert lines[2]["type"] == "add"
        assert lines[2]["content"] == "added line"
        assert lines[3]["type"] == "context"


class TestGitServiceWithRepo:
    """Tests for GitService with actual git repository."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    def test_is_git_repository(self, git_service: GitService, git_repo: Path) -> None:
        """Test checking if path is a git repository."""
        assert git_service.is_git_repository(git_repo) is True
        assert git_service.is_git_repository(git_repo.parent) is False

    def test_get_repository(self, git_service: GitService, git_repo: Path) -> None:
        """Test getting repository info."""
        repo = git_service.get_repository(git_repo)

        assert repo.path == git_repo
        assert len(repo.worktrees) >= 1

    def test_get_current_branch(self, git_service: GitService, git_repo: Path) -> None:
        """Test getting current branch."""
        branch = git_service.get_current_branch(git_repo)

        # Default branch could be main or master
        assert branch in ("main", "master")

    def test_list_branches(self, git_service: GitService, git_repo: Path) -> None:
        """Test listing branches."""
        local, remote = git_service.list_branches(git_repo, include_remote=False)

        assert len(local) >= 1
        assert local[0] in ("main", "master")

    def test_get_worktree_status_clean(
        self, git_service: GitService, git_repo: Path
    ) -> None:
        """Test getting status of clean worktree."""
        status = git_service.get_worktree_status(git_repo)

        assert status["modified"] == []
        assert status["added"] == []
        assert status["deleted"] == []
        assert status["untracked"] == []

    def test_get_worktree_status_modified(
        self, git_service: GitService, git_repo: Path
    ) -> None:
        """Test getting status with modified file."""
        # Modify a file
        (git_repo / "README.md").write_text("# Modified\n")

        status = git_service.get_worktree_status(git_repo)

        assert "README.md" in status["modified"]

    def test_get_worktree_status_untracked(
        self, git_service: GitService, git_repo: Path
    ) -> None:
        """Test getting status with untracked file."""
        # Create untracked file
        (git_repo / "new_file.txt").write_text("new content\n")

        status = git_service.get_worktree_status(git_repo)

        assert "new_file.txt" in status["untracked"]

    def test_get_diff_empty(self, git_service: GitService, git_repo: Path) -> None:
        """Test getting diff when no changes."""
        diff = git_service.get_diff(git_repo)

        assert diff == ""

    def test_get_diff_with_changes(
        self, git_service: GitService, git_repo: Path
    ) -> None:
        """Test getting diff with modifications."""
        # Modify a file
        (git_repo / "README.md").write_text("# Modified Content\n")

        diff = git_service.get_diff(git_repo)

        assert "Modified Content" in diff
        assert "-# Test Repo" in diff

    def test_get_changed_files(self, git_service: GitService, git_repo: Path) -> None:
        """Test getting list of changed files."""
        # Modify a file
        (git_repo / "README.md").write_text("# Modified\n")

        files = git_service.get_changed_files(git_repo)

        assert len(files) == 1
        assert files[0]["path"] == "README.md"
        assert files[0]["status"] == "modified"
        assert "additions" in files[0]
        assert "deletions" in files[0]

    def test_stage_and_unstage_file(
        self, git_service: GitService, git_repo: Path
    ) -> None:
        """Test staging and unstaging a file."""
        # Create and modify file
        (git_repo / "test.txt").write_text("content\n")

        # Stage it
        git_service.stage_file(git_repo, "test.txt")

        # Check staged
        staged_files = git_service.get_changed_files(git_repo, staged=True)
        assert len(staged_files) == 1
        assert staged_files[0]["path"] == "test.txt"

        # Unstage it
        git_service.unstage_file(git_repo, "test.txt")

        # Check unstaged
        staged_files = git_service.get_changed_files(git_repo, staged=True)
        assert len(staged_files) == 0

    def test_get_file_content(self, git_service: GitService, git_repo: Path) -> None:
        """Test getting file content at HEAD."""
        content = git_service.get_file_content(git_repo, "README.md")

        assert content == "# Test Repo\n"

    def test_get_file_content_nonexistent(
        self, git_service: GitService, git_repo: Path
    ) -> None:
        """Test getting content of nonexistent file."""
        content = git_service.get_file_content(git_repo, "nonexistent.txt")

        assert content == ""

    def test_discard_changes(self, git_service: GitService, git_repo: Path) -> None:
        """Test discarding changes to a file."""
        # Modify file
        (git_repo / "README.md").write_text("# Modified\n")

        # Discard changes
        git_service.discard_changes(git_repo, "README.md")

        # Check file is restored
        content = (git_repo / "README.md").read_text()
        assert content == "# Test Repo\n"

    def test_create_and_list_stash(
        self, git_service: GitService, git_repo: Path
    ) -> None:
        """Test creating and listing stashes."""
        # Modify file
        (git_repo / "README.md").write_text("# Stashed changes\n")

        # Create stash
        ref = git_service.create_stash(git_repo, message="test stash")

        assert "stash@{" in ref

        # List stashes
        stashes = git_service.list_stashes(git_repo)

        assert len(stashes) >= 1
        assert stashes[0]["message"] == "test stash"

        # File should be restored
        content = (git_repo / "README.md").read_text()
        assert content == "# Test Repo\n"

    def test_apply_stash(self, git_service: GitService, git_repo: Path) -> None:
        """Test applying a stash."""
        # Modify and stash
        (git_repo / "README.md").write_text("# Stashed\n")
        git_service.create_stash(git_repo, message="to apply")

        # Apply stash
        git_service.apply_stash(git_repo)

        # Check file is modified again
        content = (git_repo / "README.md").read_text()
        assert content == "# Stashed\n"


class TestGitServiceErrors:
    """Tests for GitService error handling."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    def test_not_a_repository(self, git_service: GitService, temp_dir: Path) -> None:
        """Test error when path is not a repository."""
        with pytest.raises(GitError, match="Not a Git repository"):
            git_service.get_repository(temp_dir)

    def test_get_diff_not_a_repo(
        self, git_service: GitService, temp_dir: Path
    ) -> None:
        """Test error getting diff from non-repo."""
        with pytest.raises(GitError):
            git_service.get_diff(temp_dir)
