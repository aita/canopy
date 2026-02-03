"""Session and Message data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4


class SessionStatus(Enum):
    """Status of a Claude Code session."""

    IDLE = "idle"
    RUNNING = "running"
    TERMINATED = "terminated"


class MessageRole(Enum):
    """Role of a message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """Represents a chat message."""

    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Create from dictionary."""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class Session:
    """Represents a Claude Code session."""

    id: UUID = field(default_factory=uuid4)
    worktree_path: Path = field(default_factory=Path)
    name: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    messages: list[Message] = field(default_factory=list)
    status: SessionStatus = SessionStatus.IDLE
    claude_session_id: Optional[str] = None  # For --resume

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"Session {self.created_at.strftime('%H:%M')}"

    def add_message(self, role: MessageRole, content: str) -> Message:
        """Add a message to the session."""
        msg = Message(role=role, content=content)
        self.messages.append(msg)
        return msg

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "worktree_path": str(self.worktree_path),
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "messages": [m.to_dict() for m in self.messages],
            "status": self.status.value,
            "claude_session_id": self.claude_session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Create from dictionary."""
        session = cls(
            id=UUID(data["id"]),
            worktree_path=Path(data["worktree_path"]),
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            status=SessionStatus(data["status"]),
            claude_session_id=data.get("claude_session_id"),
        )
        session.messages = [Message.from_dict(m) for m in data.get("messages", [])]
        return session

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Session):
            return False
        return self.id == other.id
