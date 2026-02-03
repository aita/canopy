"""Tests for StreamEvent parsing."""

import pytest

from canopy.core.claude_runner import StreamEvent


class TestStreamEventFromJson:
    """Tests for StreamEvent.from_json()."""

    def test_init_event(self) -> None:
        """Test parsing init event."""
        data = {
            "type": "init",
            "session_id": "abc123",
            "message": {"some": "data"},
        }
        event = StreamEvent.from_json(data)

        assert event.type == "init"
        assert event.session_id == "abc123"
        assert event.message == {"some": "data"}

    def test_assistant_event_with_text_blocks(self) -> None:
        """Test parsing assistant event with text content blocks."""
        data = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": "World"},
                ]
            },
        }
        event = StreamEvent.from_json(data)

        assert event.type == "assistant"
        assert event.content == "Hello\nWorld"

    def test_assistant_event_with_string_content(self) -> None:
        """Test parsing assistant event with string content."""
        data = {
            "type": "assistant",
            "message": {
                "content": ["Simple string content"]
            },
        }
        event = StreamEvent.from_json(data)

        assert event.type == "assistant"
        assert event.content == "Simple string content"

    def test_assistant_event_empty_content(self) -> None:
        """Test parsing assistant event with empty content."""
        data = {
            "type": "assistant",
            "message": {"content": []},
        }
        event = StreamEvent.from_json(data)

        assert event.type == "assistant"
        assert event.content == ""

    def test_tool_use_event(self) -> None:
        """Test parsing tool_use event."""
        data = {
            "type": "tool_use",
            "tool": {
                "name": "Read",
                "input": {"file_path": "/path/to/file.py"},
            },
        }
        event = StreamEvent.from_json(data)

        assert event.type == "tool_use"
        assert event.tool_name == "Read"
        assert event.tool_input == {"file_path": "/path/to/file.py"}

    def test_tool_result_event(self) -> None:
        """Test parsing tool_result event."""
        data = {
            "type": "tool_result",
            "tool": {
                "name": "Read",
                "result": "file contents here",
            },
        }
        event = StreamEvent.from_json(data)

        assert event.type == "tool_result"
        assert event.tool_name == "Read"
        assert event.tool_result == "file contents here"

    def test_result_event_with_string(self) -> None:
        """Test parsing result event with string result."""
        data = {
            "type": "result",
            "session_id": "xyz789",
            "cost_usd": 0.05,
            "duration_ms": 1500,
            "result": "Final response text",
        }
        event = StreamEvent.from_json(data)

        assert event.type == "result"
        assert event.session_id == "xyz789"
        assert event.cost_usd == 0.05
        assert event.duration_ms == 1500
        assert event.content == "Final response text"

    def test_result_event_with_dict(self) -> None:
        """Test parsing result event with dict result."""
        data = {
            "type": "result",
            "result": {"text": "Response from dict"},
        }
        event = StreamEvent.from_json(data)

        assert event.type == "result"
        assert event.content == "Response from dict"

    def test_error_event(self) -> None:
        """Test parsing error event."""
        data = {
            "type": "error",
            "error": {"message": "Something went wrong"},
        }
        event = StreamEvent.from_json(data)

        assert event.type == "error"
        assert event.content == "Something went wrong"

    def test_error_event_fallback(self) -> None:
        """Test parsing error event without message field."""
        data = {
            "type": "error",
            "error": {"code": 500},
        }
        event = StreamEvent.from_json(data)

        assert event.type == "error"
        assert "500" in event.content or "code" in event.content

    def test_unknown_event_type(self) -> None:
        """Test parsing unknown event type."""
        data = {
            "type": "unknown_type",
            "some": "data",
        }
        event = StreamEvent.from_json(data)

        assert event.type == "unknown_type"

    def test_missing_type(self) -> None:
        """Test parsing event with missing type."""
        data = {"session_id": "test"}
        event = StreamEvent.from_json(data)

        assert event.type == "unknown"

    def test_user_input_event(self) -> None:
        """Test parsing user_input event."""
        data = {
            "type": "user_input",
            "message": {
                "content": [{"type": "text", "text": "User message"}]
            },
        }
        event = StreamEvent.from_json(data)

        assert event.type == "user_input"
        assert event.content == "User message"
