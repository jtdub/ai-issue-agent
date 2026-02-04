"""Tests for Slack chat adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_issue_agent.config.schema import SlackConfig


@pytest.fixture
def slack_config() -> SlackConfig:
    """Create a test Slack configuration."""
    return SlackConfig(
        bot_token="xoxb-test-123-456",
        app_token="xapp-test-789",
        channels=["#errors"],
        processing_reaction="eyes",
        complete_reaction="white_check_mark",
        error_reaction="x",
    )


class TestSlackAdapterInit:
    """Test SlackAdapter initialization."""

    def test_init_with_config(self, slack_config: SlackConfig) -> None:
        """Test initializing with configuration."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp"):
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            adapter = SlackAdapter(slack_config)
            assert adapter._config == slack_config
            assert adapter._connected is False

    def test_init_creates_app(self, slack_config: SlackConfig) -> None:
        """Test that initialization creates Slack app."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            SlackAdapter(slack_config)
            mock_app.assert_called_once_with(token="xoxb-test-123-456")

    def test_init_creates_message_queue(self, slack_config: SlackConfig) -> None:
        """Test that initialization creates message queue."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp"):
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            adapter = SlackAdapter(slack_config)
            assert adapter._message_queue is not None


class TestSlackAdapterSendReply:
    """Test sending replies via SlackAdapter."""

    async def test_send_reply_simple(self, slack_config: SlackConfig) -> None:
        """Test sending a simple text reply."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.chat_postMessage = AsyncMock(
                return_value={"ok": True, "ts": "1234567890.123456"}
            )
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            result = await adapter.send_reply(
                channel_id="C123",
                text="Hello!",
            )

            assert result == "1234567890.123456"
            mock_client.chat_postMessage.assert_called_once()

    async def test_send_reply_in_thread(self, slack_config: SlackConfig) -> None:
        """Test sending a reply in a thread."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.chat_postMessage = AsyncMock(
                return_value={"ok": True, "ts": "1234567890.123456"}
            )
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            result = await adapter.send_reply(
                channel_id="C123",
                text="Thread reply",
                thread_id="1234567890.000000",
            )

            assert result == "1234567890.123456"
            call_kwargs = mock_client.chat_postMessage.call_args[1]
            assert call_kwargs.get("thread_ts") == "1234567890.000000"


class TestSlackAdapterReactions:
    """Test reaction management in SlackAdapter."""

    async def test_add_reaction(self, slack_config: SlackConfig) -> None:
        """Test adding a reaction to a message."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.reactions_add = AsyncMock(return_value={"ok": True})
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            await adapter.add_reaction(
                channel_id="C123",
                message_id="1234567890.123456",
                reaction="eyes",
            )

            mock_client.reactions_add.assert_called_once_with(
                channel="C123",
                timestamp="1234567890.123456",
                name="eyes",
            )

    async def test_remove_reaction(self, slack_config: SlackConfig) -> None:
        """Test removing a reaction from a message."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.reactions_remove = AsyncMock(return_value={"ok": True})
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            await adapter.remove_reaction(
                channel_id="C123",
                message_id="1234567890.123456",
                reaction="eyes",
            )

            mock_client.reactions_remove.assert_called_once_with(
                channel="C123",
                timestamp="1234567890.123456",
                name="eyes",
            )

    async def test_add_processing_reaction(self, slack_config: SlackConfig) -> None:
        """Test adding processing reaction."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.reactions_add = AsyncMock(return_value={"ok": True})
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            await adapter.add_processing_reaction("C123", "1234567890.123456")

            mock_client.reactions_add.assert_called_once_with(
                channel="C123",
                timestamp="1234567890.123456",
                name="eyes",
            )


class TestSlackAdapterFormatBlocks:
    """Test block formatting in SlackAdapter."""

    def test_format_issue_link_blocks(self, slack_config: SlackConfig) -> None:
        """Test formatting issue link blocks."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp"):
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            adapter = SlackAdapter(slack_config)

            blocks = adapter.format_issue_link_blocks(
                issue_url="https://github.com/owner/repo/issues/42",
                issue_title="Test Issue",
                issue_number=42,
                is_new=True,
            )

            assert isinstance(blocks, list)
            assert len(blocks) > 0

    def test_format_issue_link_blocks_existing(self, slack_config: SlackConfig) -> None:
        """Test formatting issue link blocks for existing issue."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp"):
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            adapter = SlackAdapter(slack_config)

            blocks = adapter.format_issue_link_blocks(
                issue_url="https://github.com/owner/repo/issues/10",
                issue_title="Existing Issue",
                issue_number=10,
                is_new=False,
            )

            assert isinstance(blocks, list)
            assert len(blocks) > 0


class TestSlackAdapterMessageProcessing:
    """Test message processing in SlackAdapter."""

    async def test_process_message_event_skips_bot_messages(
        self, slack_config: SlackConfig
    ) -> None:
        """Test that bot messages are skipped."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            # Process a bot message - should be skipped
            await adapter._process_message_event({"subtype": "bot_message"})

            # Queue should be empty
            assert adapter._message_queue.empty()

    async def test_process_message_event_skips_message_changed(
        self, slack_config: SlackConfig
    ) -> None:
        """Test that message_changed events are skipped."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            await adapter._process_message_event({"subtype": "message_changed"})

            assert adapter._message_queue.empty()

    async def test_process_message_event_skips_messages_with_bot_id(
        self, slack_config: SlackConfig
    ) -> None:
        """Test that messages with bot_id are skipped."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            await adapter._process_message_event({"bot_id": "B123"})

            assert adapter._message_queue.empty()


class TestSlackAdapterUserLookup:
    """Test user name lookup in SlackAdapter."""

    async def test_get_user_name_returns_display_name(self, slack_config: SlackConfig) -> None:
        """Test getting user display name."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.users_info = AsyncMock(
                return_value={
                    "user": {
                        "profile": {"display_name": "John Doe"},
                        "name": "johndoe",
                    }
                }
            )
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            name = await adapter._get_user_name("U123")

            assert name == "John Doe"

    async def test_get_user_name_empty_id_returns_unknown(self, slack_config: SlackConfig) -> None:
        """Test that empty user ID returns 'unknown'."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            name = await adapter._get_user_name("")

            assert name == "unknown"

    async def test_get_user_name_api_error_returns_user_id(self, slack_config: SlackConfig) -> None:
        """Test that API error returns user ID as fallback."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from slack_sdk.errors import SlackApiError

            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.users_info = AsyncMock(
                side_effect=SlackApiError("error", {"error": "user_not_found"})  # type: ignore[no-untyped-call]
            )
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            name = await adapter._get_user_name("U123")

            assert name == "U123"


class TestSlackAdapterCompleteReaction:
    """Test complete reaction functionality."""

    async def test_add_complete_reaction(self, slack_config: SlackConfig) -> None:
        """Test adding complete reaction."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.reactions_add = AsyncMock(return_value={"ok": True})
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            await adapter.add_complete_reaction("C123", "1234567890.123456")

            mock_client.reactions_add.assert_called_once_with(
                channel="C123",
                timestamp="1234567890.123456",
                name="white_check_mark",
            )

    async def test_add_error_reaction(self, slack_config: SlackConfig) -> None:
        """Test adding error reaction."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.reactions_add = AsyncMock(return_value={"ok": True})
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            await adapter.add_error_reaction("C123", "1234567890.123456")

            mock_client.reactions_add.assert_called_once_with(
                channel="C123",
                timestamp="1234567890.123456",
                name="x",
            )


class TestSlackAdapterSendReplyWithBlocks:
    """Test sending replies with blocks."""

    async def test_send_reply_with_blocks(self, slack_config: SlackConfig) -> None:
        """Test sending a reply with rich blocks."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.chat_postMessage = AsyncMock(
                return_value={"ok": True, "ts": "1234567890.123456"}
            )
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)
            blocks: list[dict[str, Any]] = [
                {"type": "section", "text": {"type": "mrkdwn", "text": "*Bold*"}}
            ]

            result = await adapter.send_reply(
                channel_id="C123",
                text="Fallback",
                blocks=blocks,
            )

            assert result == "1234567890.123456"
            call_kwargs = mock_client.chat_postMessage.call_args[1]
            assert call_kwargs.get("blocks") == blocks


class TestSlackAdapterDisconnect:
    """Test disconnect functionality."""

    async def test_disconnect_when_not_connected(self, slack_config: SlackConfig) -> None:
        """Test disconnect when already disconnected."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)
            assert adapter._connected is False

            # Should not raise, just return
            await adapter.disconnect()

            assert adapter._connected is False

    async def test_disconnect_sets_flag(self, slack_config: SlackConfig) -> None:
        """Test that disconnect sets the connected flag to False."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)
            # Simulate being connected
            adapter._connected = True

            await adapter.disconnect()

            assert adapter._connected is False


class TestSlackAdapterListen:
    """Test message listening functionality."""

    async def test_listen_raises_when_not_connected(self, slack_config: SlackConfig) -> None:
        """Test that listen raises error when not connected."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter, SlackAdapterError

            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)
            assert adapter._connected is False

            with pytest.raises(SlackAdapterError, match="Not connected"):
                async for _ in adapter.listen():
                    pass


class TestSlackAdapterChannelResolution:
    """Test channel name resolution."""

    async def test_resolve_channel_ids_no_channels(self) -> None:
        """Test channel resolution with no configured channels."""
        config = SlackConfig(
            bot_token="xoxb-test-123-456",
            app_token="xapp-test-789",
            channels=[],  # No channels configured
        )
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(config)

            await adapter._resolve_channel_ids()

            # Should have empty set (monitor all channels)
            assert adapter._monitored_channel_ids == set()

    async def test_resolve_channel_ids_with_channels(self, slack_config: SlackConfig) -> None:
        """Test channel resolution with configured channels."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.conversations_list = AsyncMock(
                return_value={
                    "channels": [
                        {"id": "C123", "name": "errors"},
                        {"id": "C456", "name": "general"},
                    ]
                }
            )
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)

            await adapter._resolve_channel_ids()

            assert "C123" in adapter._monitored_channel_ids


class TestSlackAdapterProcessMessage:
    """Test message processing with valid messages."""

    async def test_process_valid_message(self, slack_config: SlackConfig) -> None:
        """Test processing a valid message."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_client = MagicMock()
            mock_client.users_info = AsyncMock(
                return_value={"user": {"profile": {"display_name": "Test User"}}}
            )
            mock_app.client = mock_client
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)
            # Don't set monitored channels to allow all
            adapter._monitored_channel_ids = set()

            event = {
                "channel": "C123",
                "ts": "1234567890.123456",
                "user": "U999",
                "text": "Traceback (most recent call last):",
            }

            await adapter._process_message_event(event)

            # Message should be in queue
            assert not adapter._message_queue.empty()

    async def test_process_message_skips_unmonitored_channel(
        self, slack_config: SlackConfig
    ) -> None:
        """Test that messages from unmonitored channels are skipped."""
        with patch("ai_issue_agent.adapters.chat.slack.AsyncApp") as mock_app_class:
            from ai_issue_agent.adapters.chat.slack import SlackAdapter

            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            adapter = SlackAdapter(slack_config)
            # Set monitored channels to a specific channel
            adapter._monitored_channel_ids = {"C999"}

            event = {
                "channel": "C123",  # Different channel
                "ts": "1234567890.123456",
                "user": "U999",
                "text": "Hello",
            }

            await adapter._process_message_event(event)

            # Message should NOT be in queue
            assert adapter._message_queue.empty()
