"""Tests for message data models."""

from datetime import datetime

import pytest

from ai_issue_agent.models.message import ChatMessage, ChatReply, ProcessingResult


class TestChatMessage:
    """Test ChatMessage dataclass."""

    def test_create_chat_message(self):
        """Test creating a ChatMessage."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        raw_event = {"type": "message", "ts": "1234567890.123456"}

        message = ChatMessage(
            channel_id="C12345",
            message_id="M67890",
            thread_id="T11111",
            user_id="U99999",
            user_name="alice",
            text="Traceback (most recent call last):\n  ...",
            timestamp=timestamp,
            raw_event=raw_event,
        )

        assert message.channel_id == "C12345"
        assert message.message_id == "M67890"
        assert message.thread_id == "T11111"
        assert message.user_id == "U99999"
        assert message.user_name == "alice"
        assert "Traceback" in message.text
        assert message.timestamp == timestamp
        assert message.raw_event == raw_event

    def test_create_message_without_thread(self):
        """Test creating a message not in a thread."""
        message = ChatMessage(
            channel_id="C12345",
            message_id="M67890",
            thread_id=None,
            user_id="U99999",
            user_name="alice",
            text="Hello",
            timestamp=datetime.now(),
            raw_event={},
        )

        assert message.thread_id is None

    def test_raw_event_preserves_dict(self):
        """Test that raw_event preserves the original dict."""
        raw_event = {
            "type": "message",
            "user": "U123",
            "channel": "C456",
            "text": "test",
            "ts": "123.456",
        }

        message = ChatMessage(
            channel_id="C456",
            message_id="M789",
            thread_id=None,
            user_id="U123",
            user_name="user",
            text="test",
            timestamp=datetime.now(),
            raw_event=raw_event,
        )

        assert message.raw_event == raw_event
        assert message.raw_event["type"] == "message"

    def test_frozen_immutable(self):
        """Test that ChatMessage is frozen (immutable)."""
        message = ChatMessage(
            channel_id="C12345",
            message_id="M67890",
            thread_id=None,
            user_id="U99999",
            user_name="alice",
            text="test",
            timestamp=datetime.now(),
            raw_event={},
        )

        with pytest.raises(AttributeError):
            message.text = "changed"  # type: ignore


class TestChatReply:
    """Test ChatReply dataclass."""

    def test_create_simple_reply(self):
        """Test creating a simple reply."""
        reply = ChatReply(
            channel_id="C12345",
            text="Created issue: https://github.com/owner/repo/issues/42",
        )

        assert reply.channel_id == "C12345"
        assert "Created issue" in reply.text
        assert reply.thread_id is None
        assert reply.blocks is None

    def test_create_threaded_reply(self):
        """Test creating a reply in a thread."""
        reply = ChatReply(
            channel_id="C12345",
            text="Found existing issue",
            thread_id="T11111",
        )

        assert reply.channel_id == "C12345"
        assert reply.thread_id == "T11111"
        assert reply.blocks is None

    def test_create_reply_with_blocks(self):
        """Test creating a reply with rich formatting blocks."""
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Bold text*"}},
            {
                "type": "actions",
                "elements": [{"type": "button", "text": "View Issue"}],
            },
        ]

        reply = ChatReply(
            channel_id="C12345",
            text="Fallback text",
            blocks=blocks,
        )

        assert reply.blocks == blocks
        assert len(reply.blocks) == 2
        assert reply.blocks[0]["type"] == "section"

    def test_frozen_immutable(self):
        """Test that ChatReply is frozen (immutable)."""
        reply = ChatReply(channel_id="C12345", text="test")

        with pytest.raises(AttributeError):
            reply.text = "changed"  # type: ignore


class TestProcessingResult:
    """Test ProcessingResult enum."""

    def test_processing_result_values(self):
        """Test ProcessingResult enum values."""
        assert ProcessingResult.NO_TRACEBACK.value == "no_traceback"
        assert (
            ProcessingResult.EXISTING_ISSUE_LINKED.value == "existing_issue_linked"
        )
        assert ProcessingResult.NEW_ISSUE_CREATED.value == "new_issue_created"
        assert ProcessingResult.ERROR.value == "error"

    def test_processing_result_members(self):
        """Test ProcessingResult has all expected members."""
        expected = {
            ProcessingResult.NO_TRACEBACK,
            ProcessingResult.EXISTING_ISSUE_LINKED,
            ProcessingResult.NEW_ISSUE_CREATED,
            ProcessingResult.ERROR,
        }
        assert set(ProcessingResult) == expected

    def test_can_use_in_comparisons(self):
        """Test that enum members can be compared."""
        result = ProcessingResult.NEW_ISSUE_CREATED

        assert result == ProcessingResult.NEW_ISSUE_CREATED
        assert result != ProcessingResult.ERROR

    def test_can_use_in_conditionals(self):
        """Test using ProcessingResult in conditional logic."""
        result = ProcessingResult.NO_TRACEBACK

        if result == ProcessingResult.NO_TRACEBACK:
            processed = True
        else:
            processed = False

        assert processed
