"""Tests for UI widgets."""

from datetime import datetime

import pytest
from PySide6.QtWidgets import QApplication

from canopy.models.session import Message, MessageRole
from canopy.ui.chat_view import StreamingChatView, StreamingMessageWidget


@pytest.fixture
def qapp():
    """Create a QApplication for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestStreamingChatView:
    """Tests for StreamingChatView widget."""

    @pytest.fixture
    def chat_view(self, qapp) -> StreamingChatView:
        """Create a StreamingChatView instance."""
        return StreamingChatView()

    def test_initial_state(self, chat_view: StreamingChatView) -> None:
        """Test initial state of chat view."""
        assert chat_view._messages == []
        assert chat_view._is_streaming is False

    def test_add_message(self, chat_view: StreamingChatView) -> None:
        """Test adding a message."""
        msg = Message(role=MessageRole.USER, content="Hello")
        chat_view.add_message(msg)

        assert len(chat_view._messages) == 1
        assert chat_view._messages[0].content == "Hello"

    def test_add_multiple_messages(self, chat_view: StreamingChatView) -> None:
        """Test adding multiple messages."""
        chat_view.add_message(Message(role=MessageRole.USER, content="Hi"))
        chat_view.add_message(Message(role=MessageRole.ASSISTANT, content="Hello!"))
        chat_view.add_message(Message(role=MessageRole.USER, content="How are you?"))

        assert len(chat_view._messages) == 3

    def test_clear(self, chat_view: StreamingChatView) -> None:
        """Test clearing messages."""
        chat_view.add_message(Message(role=MessageRole.USER, content="Test"))
        chat_view.clear()

        assert len(chat_view._messages) == 0

    def test_set_messages(self, chat_view: StreamingChatView) -> None:
        """Test setting all messages at once."""
        messages = [
            Message(role=MessageRole.USER, content="First"),
            Message(role=MessageRole.ASSISTANT, content="Second"),
        ]
        chat_view.set_messages(messages)

        assert len(chat_view._messages) == 2

    def test_start_streaming(self, chat_view: StreamingChatView) -> None:
        """Test starting streaming mode."""
        chat_view.start_streaming()

        assert chat_view._is_streaming is True
        assert hasattr(chat_view, "_streaming_widget")

    def test_append_streaming_text(self, chat_view: StreamingChatView) -> None:
        """Test appending streaming text."""
        chat_view.start_streaming()

        chat_view.append_streaming_text("Hello ")
        assert chat_view._streaming_buffer.getvalue() == "Hello "

        chat_view.append_streaming_text("World")
        assert chat_view._streaming_buffer.getvalue() == "Hello World"

    def test_finish_streaming(self, chat_view: StreamingChatView) -> None:
        """Test finishing streaming."""
        chat_view.start_streaming()
        chat_view.append_streaming_text("Streamed content")

        msg = chat_view.finish_streaming()

        assert chat_view._is_streaming is False
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Streamed content"
        assert len(chat_view._messages) == 1

    def test_streaming_clears_buffer(self, chat_view: StreamingChatView) -> None:
        """Test that finishing streaming clears the buffer."""
        chat_view.start_streaming()
        chat_view.append_streaming_text("Content")
        chat_view.finish_streaming()

        assert chat_view._streaming_buffer.getvalue() == ""


class TestStreamingMessageWidget:
    """Tests for StreamingMessageWidget."""

    @pytest.fixture
    def user_message(self) -> Message:
        """Create a user message."""
        return Message(
            role=MessageRole.USER,
            content="User message",
            timestamp=datetime(2024, 1, 15, 10, 30),
        )

    @pytest.fixture
    def assistant_message(self) -> Message:
        """Create an assistant message."""
        return Message(
            role=MessageRole.ASSISTANT,
            content="Assistant response",
            timestamp=datetime(2024, 1, 15, 10, 31),
        )

    def test_create_with_user_message(
        self, qapp, user_message: Message
    ) -> None:
        """Test creating widget with user message."""
        widget = StreamingMessageWidget(user_message)

        assert widget._message == user_message
        assert widget._streaming is False

    def test_create_with_assistant_message(
        self, qapp, assistant_message: Message
    ) -> None:
        """Test creating widget with assistant message."""
        widget = StreamingMessageWidget(assistant_message)

        assert widget._message == assistant_message

    def test_create_streaming(self, qapp) -> None:
        """Test creating streaming widget."""
        widget = StreamingMessageWidget(streaming=True)

        assert widget._streaming is True
        assert widget._message is None

    def test_set_content(self, qapp) -> None:
        """Test setting content on streaming widget."""
        widget = StreamingMessageWidget(streaming=True)
        widget.set_content("New content")

        # Content should include cursor indicator when streaming
        text = widget._content.toPlainText()
        assert "New content" in text

    def test_finish_streaming(self, qapp) -> None:
        """Test finishing streaming mode."""
        widget = StreamingMessageWidget(streaming=True)
        widget.set_content("Final content")
        widget.finish_streaming()

        assert widget._streaming is False
        # Cursor should be removed
        text = widget._content.toPlainText()
        assert text == "Final content"

    def test_role_icons(self, qapp, user_message: Message, assistant_message: Message) -> None:
        """Test that different roles have different icons."""
        user_widget = StreamingMessageWidget(user_message)
        assistant_widget = StreamingMessageWidget(assistant_message)

        # Check role indicator text
        assert user_widget._get_role_icon(MessageRole.USER) == "U"
        assert assistant_widget._get_role_icon(MessageRole.ASSISTANT) == "C"
        assert user_widget._get_role_icon(MessageRole.SYSTEM) == "!"

    def test_role_names(self, qapp) -> None:
        """Test role display names."""
        widget = StreamingMessageWidget(streaming=True)

        assert widget._get_role_name(MessageRole.USER) == "You"
        assert widget._get_role_name(MessageRole.ASSISTANT) == "Claude"
        assert widget._get_role_name(MessageRole.SYSTEM) == "System"
