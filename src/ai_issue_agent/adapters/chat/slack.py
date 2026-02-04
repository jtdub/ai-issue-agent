"""Slack chat adapter using slack-bolt.

This module implements the ChatProvider protocol for Slack using the
slack-bolt library with Socket Mode for real-time events.

Features:
- Socket Mode connection for real-time message delivery
- Automatic reconnection on transient failures
- Channel filtering based on configuration
- Thread support for replies

See docs/ARCHITECTURE.md for design details.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.app.async_app import AsyncApp
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from ...config.schema import SlackConfig
from ...models.message import ChatMessage

if TYPE_CHECKING:
    from slack_bolt.context.async_context import AsyncBoltContext


log = structlog.get_logger()


class SlackAdapterError(Exception):
    """Base exception for Slack adapter errors."""


class ConnectionError(SlackAdapterError):
    """Raised when connection to Slack fails."""


class SendError(SlackAdapterError):
    """Raised when sending a message fails."""


class ReactionError(SlackAdapterError):
    """Raised when adding/removing a reaction fails."""


class SlackAdapter:
    """Slack chat adapter implementing the ChatProvider protocol.

    This adapter uses slack-bolt with Socket Mode to receive real-time
    messages and respond to them.

    Example:
        config = SlackConfig(
            bot_token="xoxb-...",
            app_token="xapp-...",
            channels=["#errors"],
        )
        adapter = SlackAdapter(config)

        await adapter.connect()
        async for message in adapter.listen():
            print(f"Received: {message.text}")
        await adapter.disconnect()
    """

    def __init__(self, config: SlackConfig) -> None:
        """Initialize the Slack adapter.

        Args:
            config: Slack-specific configuration.
        """
        self._config = config
        self._connected = False

        # Create the Slack app
        self._app = AsyncApp(token=config.bot_token)
        self._client: AsyncWebClient = self._app.client
        self._socket_handler: AsyncSocketModeHandler | None = None

        # Message queue for incoming messages
        self._message_queue: asyncio.Queue[ChatMessage] = asyncio.Queue()

        # Track monitored channels (resolved from names to IDs)
        self._monitored_channel_ids: set[str] = set()

        # Event to signal disconnection
        self._disconnect_event = asyncio.Event()

        # Register message handler
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register event handlers with the Slack app."""

        @self._app.event("message")
        async def handle_message(
            event: dict[str, Any],
            context: AsyncBoltContext,
        ) -> None:
            """Handle incoming message events."""
            await self._process_message_event(event)

    async def _process_message_event(self, event: dict[str, Any]) -> None:
        """Process a message event and add to queue if relevant.

        Args:
            event: The Slack message event.
        """
        # Skip bot messages and message changes
        subtype = event.get("subtype")
        if subtype in ("bot_message", "message_changed", "message_deleted"):
            return

        # Skip if we have a bot_id (this is a bot message)
        if event.get("bot_id"):
            return

        channel_id = event.get("channel", "")

        # If we have monitored channels, check if this channel is monitored
        if self._monitored_channel_ids and channel_id not in self._monitored_channel_ids:
            return

        # Extract message info
        message_id = event.get("ts", "")
        thread_id = event.get("thread_ts")
        user_id = event.get("user", "")
        text = event.get("text", "")

        # Get user info for display name
        user_name = await self._get_user_name(user_id)

        # Parse timestamp
        try:
            timestamp = datetime.fromtimestamp(float(message_id))
        except (ValueError, TypeError):
            timestamp = datetime.now()

        message = ChatMessage(
            channel_id=channel_id,
            message_id=message_id,
            thread_id=thread_id,
            user_id=user_id,
            user_name=user_name,
            text=text,
            timestamp=timestamp,
            raw_event=event,
        )

        await self._message_queue.put(message)
        log.debug(
            "message_queued",
            channel_id=channel_id,
            message_id=message_id,
            user=user_name,
        )

    async def _get_user_name(self, user_id: str) -> str:
        """Get display name for a user.

        Args:
            user_id: Slack user ID.

        Returns:
            User display name or ID if lookup fails.
        """
        if not user_id:
            return "unknown"

        try:
            result = await self._client.users_info(user=user_id)
            user: dict[str, Any] = result.get("user", {})
            # Prefer display_name, fall back to real_name, then name
            return (
                user.get("profile", {}).get("display_name")
                or user.get("profile", {}).get("real_name")
                or user.get("name")
                or user_id
            )
        except SlackApiError:
            return user_id

    async def _resolve_channel_ids(self) -> None:
        """Resolve channel names to IDs."""
        if not self._config.channels:
            # No specific channels configured, monitor all
            self._monitored_channel_ids = set()
            return

        self._monitored_channel_ids = set()

        for channel in self._config.channels:
            # Remove # prefix if present
            channel_name = channel.lstrip("#")

            try:
                # First try to find in public channels
                result = await self._client.conversations_list(
                    types="public_channel,private_channel"
                )
                channels_list: list[dict[str, Any]] = result.get("channels", [])
                for ch_dict in channels_list:
                    if ch_dict.get("name") == channel_name or ch_dict.get("id") == channel:
                        self._monitored_channel_ids.add(ch_dict["id"])
                        log.debug("channel_resolved", name=channel, id=ch_dict["id"])
                        break
            except SlackApiError as e:
                log.warning("channel_resolution_failed", channel=channel, error=str(e))

    async def connect(self) -> None:
        """Establish connection to Slack using Socket Mode.

        Raises:
            ConnectionError: If connection fails.
        """
        if self._connected:
            return

        try:
            # Resolve channel names to IDs
            await self._resolve_channel_ids()

            # Create Socket Mode handler
            self._socket_handler = AsyncSocketModeHandler(
                app=self._app,
                app_token=self._config.app_token,
            )

            # Start the handler in the background
            # Note: start_async() returns immediately after connecting
            await self._socket_handler.connect_async()  # type: ignore[no-untyped-call]

            self._connected = True
            self._disconnect_event.clear()

            log.info(
                "slack_connected",
                monitored_channels=len(self._monitored_channel_ids),
            )

        except Exception as e:
            log.error("slack_connection_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to Slack: {e}") from e

    async def disconnect(self) -> None:
        """Gracefully close the Slack connection."""
        if not self._connected:
            return

        self._disconnect_event.set()

        if self._socket_handler:
            try:
                await self._socket_handler.close_async()  # type: ignore[no-untyped-call]
            except Exception as e:
                log.warning("disconnect_error", error=str(e))

        self._connected = False
        log.info("slack_disconnected")

    async def listen(self) -> AsyncIterator[ChatMessage]:
        """Yield incoming messages from monitored channels.

        This is an async generator that yields messages as they arrive.

        Yields:
            ChatMessage: Each incoming message from monitored channels.
        """
        if not self._connected:
            raise SlackAdapterError("Not connected. Call connect() first.")

        while not self._disconnect_event.is_set():
            try:
                # Wait for a message with timeout to check disconnect
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0,
                )
                yield message
            except TimeoutError:
                # No message, check if we should continue
                continue
            except asyncio.CancelledError:
                break

    async def send_reply(
        self,
        channel_id: str,
        text: str,
        thread_id: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
    ) -> str:
        """Send a reply to a channel, optionally in a thread.

        Args:
            channel_id: Target channel identifier.
            text: Plain text message (fallback for rich formatting).
            thread_id: Parent message ID for threading (optional).
            blocks: Optional rich content blocks (Slack Block Kit).

        Returns:
            Message ID (ts) of the sent message.

        Raises:
            SendError: If message delivery fails.
        """
        try:
            kwargs: dict[str, Any] = {
                "channel": channel_id,
                "text": text,
            }

            if thread_id:
                kwargs["thread_ts"] = thread_id

            if blocks:
                kwargs["blocks"] = blocks

            result = await self._client.chat_postMessage(**kwargs)
            message_ts = result.get("ts", "")

            log.debug(
                "message_sent",
                channel_id=channel_id,
                message_ts=message_ts,
                thread_id=thread_id,
            )

            return message_ts

        except SlackApiError as e:
            log.error(
                "send_reply_failed",
                channel_id=channel_id,
                error=str(e),
            )
            raise SendError(f"Failed to send message: {e}") from e

    async def add_reaction(
        self,
        channel_id: str,
        message_id: str,
        reaction: str,
    ) -> None:
        """Add a reaction/emoji to a message.

        Args:
            channel_id: Channel containing the message.
            message_id: Target message identifier (ts).
            reaction: Reaction name (without colons, e.g., "eyes").

        Raises:
            ReactionError: If adding reaction fails.
        """
        try:
            await self._client.reactions_add(
                channel=channel_id,
                timestamp=message_id,
                name=reaction,
            )
            log.debug(
                "reaction_added",
                channel_id=channel_id,
                message_id=message_id,
                reaction=reaction,
            )

        except SlackApiError as e:
            # Ignore "already_reacted" error
            if e.response.get("error") == "already_reacted":
                return

            log.error(
                "add_reaction_failed",
                channel_id=channel_id,
                message_id=message_id,
                reaction=reaction,
                error=str(e),
            )
            raise ReactionError(f"Failed to add reaction: {e}") from e

    async def remove_reaction(
        self,
        channel_id: str,
        message_id: str,
        reaction: str,
    ) -> None:
        """Remove a previously added reaction.

        Args:
            channel_id: Channel containing the message.
            message_id: Target message identifier (ts).
            reaction: Reaction name (without colons, e.g., "eyes").

        Raises:
            ReactionError: If removing reaction fails.
        """
        try:
            await self._client.reactions_remove(
                channel=channel_id,
                timestamp=message_id,
                name=reaction,
            )
            log.debug(
                "reaction_removed",
                channel_id=channel_id,
                message_id=message_id,
                reaction=reaction,
            )

        except SlackApiError as e:
            # Ignore "no_reaction" error (reaction wasn't there)
            if e.response.get("error") == "no_reaction":
                return

            log.error(
                "remove_reaction_failed",
                channel_id=channel_id,
                message_id=message_id,
                reaction=reaction,
                error=str(e),
            )
            raise ReactionError(f"Failed to remove reaction: {e}") from e

    async def add_processing_reaction(
        self,
        channel_id: str,
        message_id: str,
    ) -> None:
        """Add the configured processing reaction (e.g., :eyes:).

        Args:
            channel_id: Channel containing the message.
            message_id: Target message identifier.
        """
        await self.add_reaction(
            channel_id=channel_id,
            message_id=message_id,
            reaction=self._config.processing_reaction,
        )

    async def add_complete_reaction(
        self,
        channel_id: str,
        message_id: str,
    ) -> None:
        """Add the configured complete reaction (e.g., :white_check_mark:).

        Args:
            channel_id: Channel containing the message.
            message_id: Target message identifier.
        """
        await self.add_reaction(
            channel_id=channel_id,
            message_id=message_id,
            reaction=self._config.complete_reaction,
        )

    async def add_error_reaction(
        self,
        channel_id: str,
        message_id: str,
    ) -> None:
        """Add the configured error reaction (e.g., :x:).

        Args:
            channel_id: Channel containing the message.
            message_id: Target message identifier.
        """
        await self.add_reaction(
            channel_id=channel_id,
            message_id=message_id,
            reaction=self._config.error_reaction,
        )

    async def remove_processing_reaction(
        self,
        channel_id: str,
        message_id: str,
    ) -> None:
        """Remove the processing reaction.

        Args:
            channel_id: Channel containing the message.
            message_id: Target message identifier.
        """
        await self.remove_reaction(
            channel_id=channel_id,
            message_id=message_id,
            reaction=self._config.processing_reaction,
        )

    def format_issue_link_blocks(
        self,
        issue_url: str,
        issue_number: int,
        issue_title: str,
        is_new: bool = True,
    ) -> list[dict[str, Any]]:
        """Format rich blocks for issue link reply.

        Args:
            issue_url: URL to the GitHub issue.
            issue_number: Issue number.
            issue_title: Issue title.
            is_new: Whether this is a newly created issue.

        Returns:
            Slack Block Kit blocks for rich formatting.
        """
        status = "Created" if is_new else "Found existing"
        emoji = ":new:" if is_new else ":link:"

        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{emoji} *{status} issue #{issue_number}*\n<{issue_url}|{issue_title}>"
                    ),
                },
            },
        ]
