"""Tests for ClaudeRunner."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication

from canopy.core.claude_runner import ClaudeResponse, ClaudeRunner, StreamEvent


@pytest.fixture
def qapp():
    """Create a QApplication for Qt tests."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    yield app


@pytest.fixture
def claude_runner(qapp) -> ClaudeRunner:
    """Create a ClaudeRunner instance."""
    return ClaudeRunner()


class TestClaudeRunnerInit:
    """Tests for ClaudeRunner initialization."""

    def test_default_command(self, claude_runner: ClaudeRunner) -> None:
        """Test default claude command."""
        assert claude_runner.claude_command == "claude"

    def test_custom_command(self, qapp) -> None:
        """Test custom claude command."""
        runner = ClaudeRunner(claude_command="/usr/local/bin/claude")
        assert runner.claude_command == "/usr/local/bin/claude"

    def test_initial_state(self, claude_runner: ClaudeRunner) -> None:
        """Test initial state."""
        assert claude_runner.is_running is False
        assert claude_runner.session_id is None
        assert claude_runner.events == []


class TestClaudeRunnerParseStreaming:
    """Tests for ClaudeRunner._parse_streaming_output()."""

    def test_parse_single_json_line(self, claude_runner: ClaudeRunner) -> None:
        """Test parsing a single JSON line."""
        claude_runner._output_format = "stream-json"
        received_events = []
        claude_runner.stream_event.connect(lambda e: received_events.append(e))

        data = '{"type": "init", "session_id": "test123"}\n'
        claude_runner._parse_streaming_output(data)

        assert len(received_events) == 1
        assert received_events[0].type == "init"
        assert received_events[0].session_id == "test123"

    def test_parse_multiple_json_lines(self, claude_runner: ClaudeRunner) -> None:
        """Test parsing multiple JSON lines."""
        claude_runner._output_format = "stream-json"
        received_events = []
        claude_runner.stream_event.connect(lambda e: received_events.append(e))

        data = '{"type": "init"}\n{"type": "assistant", "message": {"content": []}}\n'
        claude_runner._parse_streaming_output(data)

        assert len(received_events) == 2
        assert received_events[0].type == "init"
        assert received_events[1].type == "assistant"

    def test_parse_partial_line(self, claude_runner: ClaudeRunner) -> None:
        """Test handling partial JSON line (incomplete data)."""
        claude_runner._output_format = "stream-json"
        received_events = []
        claude_runner.stream_event.connect(lambda e: received_events.append(e))

        # Send partial data
        claude_runner._parse_streaming_output('{"type": "in')
        assert len(received_events) == 0  # Not yet complete

        # Complete the line
        claude_runner._parse_streaming_output('it"}\n')
        assert len(received_events) == 1
        assert received_events[0].type == "init"

    def test_parse_invalid_json(self, claude_runner: ClaudeRunner) -> None:
        """Test handling invalid JSON."""
        claude_runner._output_format = "stream-json"
        chunks = []
        claude_runner.stream_chunk.connect(lambda c: chunks.append(c))

        data = "not valid json\n"
        claude_runner._parse_streaming_output(data)

        assert len(chunks) == 1
        assert "not valid json" in chunks[0]

    def test_assistant_text_signal(self, claude_runner: ClaudeRunner) -> None:
        """Test assistant_text signal emission."""
        claude_runner._output_format = "stream-json"
        texts = []
        claude_runner.assistant_text.connect(lambda t: texts.append(t))

        data = '{"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello"}]}}\n'
        claude_runner._parse_streaming_output(data)

        assert len(texts) == 1
        assert texts[0] == "Hello"

    def test_tool_use_signal(self, claude_runner: ClaudeRunner) -> None:
        """Test tool_use_started signal emission."""
        claude_runner._output_format = "stream-json"
        tools = []
        claude_runner.tool_use_started.connect(lambda n, i: tools.append((n, i)))

        data = '{"type": "tool_use", "tool": {"name": "Read", "input": {"path": "/test"}}}\n'
        claude_runner._parse_streaming_output(data)

        assert len(tools) == 1
        assert tools[0][0] == "Read"
        assert tools[0][1] == {"path": "/test"}

    def test_tool_result_signal(self, claude_runner: ClaudeRunner) -> None:
        """Test tool_result_received signal emission."""
        claude_runner._output_format = "stream-json"
        results = []
        claude_runner.tool_result_received.connect(lambda n, r: results.append((n, r)))

        data = '{"type": "tool_result", "tool": {"name": "Read", "result": "content"}}\n'
        claude_runner._parse_streaming_output(data)

        assert len(results) == 1
        assert results[0][0] == "Read"
        assert results[0][1] == "content"


class TestClaudeRunnerParseFinal:
    """Tests for ClaudeRunner._parse_final_output()."""

    def test_parse_single_json(self, claude_runner: ClaudeRunner) -> None:
        """Test parsing single JSON object."""
        responses = []
        claude_runner.response_received.connect(lambda r: responses.append(r))

        claude_runner._output_buffer.write('{"type": "result", "session_id": "abc"}')
        claude_runner._parse_final_output()

        assert len(responses) == 1
        assert responses[0]["type"] == "result"
        assert claude_runner.session_id == "abc"

    def test_parse_jsonl_last_line(self, claude_runner: ClaudeRunner) -> None:
        """Test parsing JSONL, getting last valid line."""
        responses = []
        claude_runner.response_received.connect(lambda r: responses.append(r))

        claude_runner._output_buffer.write(
            '{"type": "init"}\n{"type": "assistant"}\n{"type": "result", "session_id": "xyz"}\n'
        )
        claude_runner._parse_final_output()

        # Should get the last valid JSON
        assert claude_runner.session_id == "xyz"

    def test_parse_empty_buffer(self, claude_runner: ClaudeRunner) -> None:
        """Test parsing empty buffer."""
        responses = []
        claude_runner.response_received.connect(lambda r: responses.append(r))

        claude_runner._parse_final_output()

        assert len(responses) == 0


class TestClaudeRunnerStringIO:
    """Tests for StringIO buffer handling."""

    def test_output_buffer_accumulates(self, claude_runner: ClaudeRunner) -> None:
        """Test that output buffer accumulates data."""
        claude_runner._output_buffer.write("first ")
        claude_runner._output_buffer.write("second")

        assert claude_runner._output_buffer.getvalue() == "first second"

    def test_buffer_reset_on_send(self, claude_runner: ClaudeRunner, temp_dir: Path) -> None:
        """Test buffers are reset when sending new message."""
        # Simulate previous data
        claude_runner._output_buffer.write("old data")
        claude_runner._line_buffer.write("old line")
        claude_runner._events.append(StreamEvent(type="old"))

        # Mock process to avoid actually starting
        with patch.object(claude_runner, "_start_process"):
            claude_runner.send_message("test", temp_dir)

        assert claude_runner._output_buffer.getvalue() == ""
        assert claude_runner._line_buffer.getvalue() == ""
        assert claude_runner._events == []


class TestClaudeResponse:
    """Tests for ClaudeResponse helper class."""

    def test_is_result(self) -> None:
        """Test is_result property."""
        response = ClaudeResponse({"type": "result"})
        assert response.is_result is True

        response = ClaudeResponse({"type": "assistant"})
        assert response.is_result is False

    def test_is_assistant_message(self) -> None:
        """Test is_assistant_message property."""
        response = ClaudeResponse({"type": "assistant"})
        assert response.is_assistant_message is True

        response = ClaudeResponse({"type": "result"})
        assert response.is_assistant_message is False

    def test_content_from_result(self) -> None:
        """Test extracting content from result field."""
        response = ClaudeResponse({"type": "result", "result": "Response text"})
        assert response.content == "Response text"

    def test_content_from_content_blocks(self) -> None:
        """Test extracting content from content blocks."""
        response = ClaudeResponse({
            "type": "assistant",
            "content": [
                {"type": "text", "text": "First"},
                {"type": "text", "text": "Second"},
            ],
        })
        assert response.content == "First\nSecond"

    def test_content_from_string_list(self) -> None:
        """Test extracting content from string list."""
        response = ClaudeResponse({
            "type": "assistant",
            "content": ["Plain", "strings"],
        })
        assert response.content == "Plain\nstrings"

    def test_content_empty(self) -> None:
        """Test content when no content field."""
        response = ClaudeResponse({"type": "result"})
        assert response.content == ""

    def test_cost_usd(self) -> None:
        """Test cost_usd property."""
        response = ClaudeResponse({"cost_usd": 0.05})
        assert response.cost_usd == 0.05

        response = ClaudeResponse({})
        assert response.cost_usd is None

    def test_duration_ms(self) -> None:
        """Test duration_ms property."""
        response = ClaudeResponse({"duration_ms": 1500})
        assert response.duration_ms == 1500

        response = ClaudeResponse({})
        assert response.duration_ms is None

    def test_session_id(self) -> None:
        """Test session_id property."""
        response = ClaudeResponse({"session_id": "abc123"})
        assert response.session_id == "abc123"
