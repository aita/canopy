"""Claude Code CLI runner for executing claude commands."""

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QProcess, Signal


class ClaudeRunner(QObject):
    """Runs Claude Code CLI commands and handles I/O."""

    # Signals
    output_received = Signal(str)  # Raw output text
    response_received = Signal(dict)  # Parsed JSON response
    error_occurred = Signal(str)  # Error message
    process_started = Signal()
    process_finished = Signal(int)  # Exit code
    stream_chunk = Signal(str)  # Streaming text chunk

    def __init__(
        self,
        claude_command: str = "claude",
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.claude_command = claude_command
        self._process: Optional[QProcess] = None
        self._output_buffer = ""
        self._current_cwd: Optional[Path] = None
        self._session_id: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """Check if a command is currently running."""
        return self._process is not None and self._process.state() == QProcess.ProcessState.Running

    @property
    def session_id(self) -> Optional[str]:
        """Get the current Claude session ID for --resume."""
        return self._session_id

    def send_message(
        self,
        message: str,
        cwd: Path,
        output_format: str = "json",
        resume_session: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
    ) -> None:
        """Send a message to Claude Code.

        Args:
            message: The message to send
            cwd: Working directory for the command
            output_format: Output format (json, text, stream-json)
            resume_session: Session ID to resume (optional)
            allowed_tools: List of allowed tools (optional)
        """
        if self.is_running:
            self.error_occurred.emit("A command is already running")
            return

        self._current_cwd = cwd
        self._output_buffer = ""

        # Build command arguments
        # Note: Working directory is set via setWorkingDirectory()
        args = [
            "--output-format", output_format,
            "--print", message,
        ]

        if resume_session:
            args.extend(["--resume", resume_session])

        if allowed_tools:
            for tool in allowed_tools:
                args.extend(["--allowedTools", tool])

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

        self._process.start()
        self.process_started.emit()

    def _on_stdout(self) -> None:
        """Handle stdout data."""
        if not self._process:
            return

        data = self._process.readAllStandardOutput().data().decode("utf-8")
        self._output_buffer += data
        self.output_received.emit(data)

        # Try to parse streaming JSON chunks
        self._parse_streaming_output(data)

    def _on_stderr(self) -> None:
        """Handle stderr data."""
        if not self._process:
            return

        data = self._process.readAllStandardError().data().decode("utf-8")
        self.error_occurred.emit(data)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        """Handle process completion."""
        # Try to parse the complete output as JSON
        self._parse_final_output()
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
        self.error_occurred.emit(error_messages.get(error, "Unknown error"))

    def _parse_streaming_output(self, data: str) -> None:
        """Parse streaming JSON output."""
        # Handle JSONL (newline-delimited JSON)
        for line in data.split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
                self._handle_json_message(obj)
            except json.JSONDecodeError:
                # Not JSON, emit as raw text
                self.stream_chunk.emit(line)

    def _parse_final_output(self) -> None:
        """Parse the final complete output."""
        if not self._output_buffer:
            return

        # Try to parse as a single JSON object
        try:
            result = json.loads(self._output_buffer)
            self._handle_json_message(result)
            return
        except json.JSONDecodeError:
            pass

        # Try to parse as JSONL and get the last message
        lines = self._output_buffer.strip().split("\n")
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
            # Give it a moment to terminate gracefully
            if not self._process.waitForFinished(3000):
                self._process.kill()

    def write_stdin(self, data: str) -> None:
        """Write data to the process stdin (for interactive mode)."""
        if self._process and self.is_running:
            self._process.write(data.encode("utf-8"))


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
    def cost_usd(self) -> Optional[float]:
        """Get the cost in USD if available."""
        return self.raw.get("cost_usd")

    @property
    def duration_ms(self) -> Optional[int]:
        """Get the duration in milliseconds if available."""
        return self.raw.get("duration_ms")
