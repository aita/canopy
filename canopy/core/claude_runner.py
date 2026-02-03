"""Claude Code CLI runner for executing claude commands."""

import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import logbook
from PySide6.QtCore import QObject, QProcess, Signal

log = logbook.Logger(__name__)


@dataclass
class StreamEvent:
    """Represents a stream-json event from Claude CLI."""

    type: str  # init, user_input, assistant, tool_use, tool_result, result, error, permission_request
    message: dict | None = None
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_result: str | None = None
    content: str = ""
    session_id: str | None = None
    cost_usd: float | None = None
    duration_ms: int | None = None
    permission_request_id: str | None = None

    @classmethod
    def from_json(cls, data: dict) -> "StreamEvent":
        """Create from JSON data."""
        event = cls(type=data.get("type", "unknown"))
        event.session_id = data.get("session_id")

        if event.type == "init":
            event.session_id = data.get("session_id")
            event.message = data.get("message")
        elif event.type in ("assistant", "user_input"):
            event.message = data.get("message", {})
            content_blocks = event.message.get("content", [])
            texts = []
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif isinstance(block, str):
                    texts.append(block)
            event.content = "\n".join(texts)
        elif event.type == "tool_use":
            event.tool_name = data.get("tool", {}).get("name")
            event.tool_input = data.get("tool", {}).get("input")
        elif event.type == "tool_result":
            event.tool_name = data.get("tool", {}).get("name")
            event.tool_result = data.get("tool", {}).get("result")
        elif event.type == "result":
            event.session_id = data.get("session_id")
            event.cost_usd = data.get("cost_usd")
            event.duration_ms = data.get("duration_ms")
            # Result content
            result = data.get("result", "")
            if isinstance(result, str):
                event.content = result
            elif isinstance(result, dict):
                event.content = result.get("text", "")
        elif event.type == "error":
            event.content = data.get("error", {}).get("message", str(data))
        elif event.type == "permission_request":
            # Permission request from CLI
            tool_info = data.get("tool", {})
            event.tool_name = tool_info.get("name")
            event.tool_input = tool_info.get("input")
            event.permission_request_id = data.get("request_id")

        return event


class ClaudeRunner(QObject):
    """Runs Claude Code CLI commands and handles I/O."""

    # Signals
    output_received = Signal(str)  # Raw output text
    response_received = Signal(dict)  # Parsed JSON response
    error_occurred = Signal(str)  # Error message (process errors, not stderr)
    process_started = Signal()
    process_finished = Signal(int)  # Exit code
    stream_chunk = Signal(str)  # Streaming text chunk

    # New stream-json signals
    stream_event = Signal(object)  # StreamEvent object
    assistant_text = Signal(str)  # Incremental assistant text
    tool_use_started = Signal(str, dict)  # tool_name, tool_input
    tool_result_received = Signal(str, str)  # tool_name, result
    permission_requested = Signal(str, str, dict)  # request_id, tool_name, tool_input

    def __init__(
        self,
        claude_command: str = "claude",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.claude_command = claude_command
        self._process: QProcess | None = None
        self._output_buffer = StringIO()  # Full output buffer
        self._line_buffer = StringIO()  # For incomplete JSON lines
        self._stderr_buffer = StringIO()  # Buffer stderr until process finishes
        self._current_cwd: Path | None = None
        self._session_id: str | None = None
        self._output_format: str = "json"
        self._events: list[StreamEvent] = []  # Collected stream events

    @property
    def is_running(self) -> bool:
        """Check if a command is currently running."""
        return self._process is not None and self._process.state() == QProcess.ProcessState.Running

    @property
    def session_id(self) -> str | None:
        """Get the current Claude session ID for --resume."""
        return self._session_id

    @property
    def events(self) -> list[StreamEvent]:
        """Get the collected stream events."""
        return self._events.copy()

    def send_message(
        self,
        message: str,
        cwd: Path,
        output_format: str = "stream-json",
        resume_session: str | None = None,
        allowed_tools: list[str] | None = None,
        model: str | None = None,
    ) -> None:
        """Send a message to Claude Code.

        Args:
            message: The message to send
            cwd: Working directory for the command
            output_format: Output format (json, text, stream-json)
            resume_session: Session ID to resume (optional)
            allowed_tools: List of allowed tools (optional)
            model: Model ID to use (optional)
        """
        if self.is_running:
            self.error_occurred.emit("A command is already running")
            return

        self._current_cwd = cwd
        self._output_buffer = StringIO()
        self._line_buffer = StringIO()
        self._stderr_buffer = StringIO()
        self._output_format = output_format
        self._events = []

        # Build command arguments
        # Note: Working directory is set via setWorkingDirectory()
        # Use --permission-mode default to avoid interactive prompts
        # --print is a boolean flag, message is passed as positional argument
        args = [
            "--output-format", output_format,
            "--permission-mode", "default",
            "--print",
        ]

        # stream-json with --print requires --verbose
        if output_format == "stream-json":
            args.append("--verbose")

        if resume_session:
            args.extend(["--resume", resume_session])

        if allowed_tools:
            for tool in allowed_tools:
                args.extend(["--allowedTools", tool])

        if model:
            args.extend(["--model", model])

        # Message is passed as positional argument at the end
        args.append(message)

        self._start_process(args)

    def _start_process(self, args: list[str]) -> None:
        """Start the Claude CLI process."""
        self._process = QProcess(self)
        self._process.setProgram(self.claude_command)
        self._process.setArguments(args)

        if self._current_cwd:
            self._process.setWorkingDirectory(str(self._current_cwd))

        # Connect signals
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        log.debug("Starting Claude CLI: {} {}", self.claude_command, " ".join(args))
        log.debug("Working directory: {}", self._current_cwd)
        self._process.start()
        # Close stdin to signal EOF - CLI should not wait for stdin input
        # Permission requests are handled via stream-json events, not stdin
        self._process.closeWriteChannel()
        self.process_started.emit()

    def _on_stdout(self) -> None:
        """Handle stdout data."""
        if not self._process:
            return

        data = self._process.readAllStandardOutput().data().decode("utf-8")
        log.debug("Claude CLI stdout: {}", data)
        self._output_buffer.write(data)
        self.output_received.emit(data)

        # Try to parse streaming JSON chunks
        self._parse_streaming_output(data)

    def _on_stderr(self) -> None:
        """Handle stderr data."""
        if not self._process:
            return

        data = self._process.readAllStandardError().data().decode("utf-8")
        log.debug("Claude CLI stderr: {}", data)
        # Buffer stderr instead of emitting immediately to avoid premature status reset
        self._stderr_buffer.write(data)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        """Handle process completion."""
        log.debug("Claude CLI finished with exit_code={}, exit_status={}", exit_code, exit_status)
        # Skip final output parsing for stream-json format since all events
        # are already processed during streaming (avoids duplicate messages)
        if self._output_format != "stream-json":
            self._parse_final_output()

        # Emit buffered stderr as error if process failed
        stderr_content = self._stderr_buffer.getvalue().strip()
        if exit_code != 0 and stderr_content:
            log.error("Claude CLI error: {}", stderr_content)
            self.error_occurred.emit(stderr_content)

        self.process_finished.emit(exit_code)
        self._process = None

    def _on_error(self, error: QProcess.ProcessError) -> None:
        """Handle process errors."""
        error_messages = {
            QProcess.ProcessError.FailedToStart: "Failed to start Claude CLI. Is it installed?",
            QProcess.ProcessError.Crashed: "Claude CLI crashed unexpectedly",
            QProcess.ProcessError.Timedout: "Claude CLI timed out",
            QProcess.ProcessError.WriteError: "Error writing to Claude CLI",
            QProcess.ProcessError.ReadError: "Error reading from Claude CLI",
            QProcess.ProcessError.UnknownError: "Unknown error occurred",
        }
        error_msg = error_messages.get(error, "Unknown error")
        log.error("Claude CLI process error: {}", error_msg)
        self.error_occurred.emit(error_msg)

    def _parse_streaming_output(self, data: str) -> None:
        """Parse streaming JSON output."""
        # Append to line buffer for handling partial lines
        self._line_buffer.write(data)

        # Get current buffer content and process complete lines
        buffer_content = self._line_buffer.getvalue()

        while "\n" in buffer_content:
            line, buffer_content = buffer_content.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
                self._handle_json_message(obj)

                # Handle stream-json events
                if self._output_format == "stream-json":
                    event = StreamEvent.from_json(obj)
                    self._events.append(event)
                    self.stream_event.emit(event)

                    # Emit specific signals based on event type
                    if event.type == "assistant" and event.content:
                        self.assistant_text.emit(event.content)
                    elif event.type == "tool_use" and event.tool_name:
                        self.tool_use_started.emit(event.tool_name, event.tool_input or {})
                    elif event.type == "tool_result" and event.tool_name:
                        self.tool_result_received.emit(event.tool_name, event.tool_result or "")
                    elif event.type == "permission_request" and event.tool_name:
                        self.permission_requested.emit(
                            event.permission_request_id or "",
                            event.tool_name,
                            event.tool_input or {},
                        )

            except json.JSONDecodeError:
                # Not JSON, emit as raw text
                self.stream_chunk.emit(line)

        # Update buffer with remaining incomplete line
        self._line_buffer = StringIO()
        self._line_buffer.write(buffer_content)

    def _parse_final_output(self) -> None:
        """Parse the final complete output."""
        output_content = self._output_buffer.getvalue()
        if not output_content:
            return

        # Try to parse as a single JSON object
        try:
            result = json.loads(output_content)
            self._handle_json_message(result)
            return
        except json.JSONDecodeError:
            pass

        # Try to parse as JSONL and get the last message
        lines = output_content.strip().split("\n")
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                result = json.loads(line)
                self._handle_json_message(result)
                return
            except json.JSONDecodeError:
                continue

    def _handle_json_message(self, obj: dict) -> None:
        """Handle a parsed JSON message."""
        # Extract session ID if present
        if "session_id" in obj:
            self._session_id = obj["session_id"]

        self.response_received.emit(obj)

    def cancel(self) -> None:
        """Cancel the current running command."""
        if self._process and self.is_running:
            self._process.terminate()
            # Use non-blocking kill after timeout to avoid freezing UI
            from PySide6.QtCore import QTimer
            QTimer.singleShot(3000, self._force_kill_if_running)

    def _force_kill_if_running(self) -> None:
        """Force kill the process if still running after terminate."""
        if self._process and self.is_running:
            self._process.kill()

    def write_stdin(self, data: str) -> None:
        """Write data to the process stdin (for interactive mode)."""
        if self._process and self.is_running:
            log.debug("Writing to Claude CLI stdin: {}", data)
            self._process.write(data.encode("utf-8"))

    def respond_permission(self, accept: bool) -> None:
        """Respond to a permission request.

        Args:
            accept: True to accept, False to reject
        """
        if self._process and self.is_running:
            # Send 'y' for accept, 'n' for reject followed by newline
            response = "y\n" if accept else "n\n"
            log.debug("Responding to permission request: {}", response.strip())
            self._process.write(response.encode("utf-8"))


class ClaudeResponse:
    """Helper class to parse Claude CLI JSON responses."""

    def __init__(self, data: dict) -> None:
        self.raw = data
        self.type = data.get("type", "")
        self.session_id = data.get("session_id")

    @property
    def is_result(self) -> bool:
        """Check if this is a final result message."""
        return self.type == "result"

    @property
    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.type == "assistant"

    @property
    def content(self) -> str:
        """Extract the text content from the response."""
        if "result" in self.raw:
            return self.raw["result"]
        if "content" in self.raw:
            content = self.raw["content"]
            if isinstance(content, list):
                # Handle content blocks
                texts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        texts.append(block)
                return "\n".join(texts)
            return str(content)
        return ""

    @property
    def cost_usd(self) -> float | None:
        """Get the cost in USD if available."""
        return self.raw.get("cost_usd")

    @property
    def duration_ms(self) -> int | None:
        """Get the duration in milliseconds if available."""
        return self.raw.get("duration_ms")
