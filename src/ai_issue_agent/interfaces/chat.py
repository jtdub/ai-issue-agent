"""Abstract interface for chat platform integrations."""

from collections.abc import AsyncIterator
from typing import Any, Protocol

from ..models.message import ChatMessage


class ChatProvider(Protocol):
    """Abstract interface for chat platform integrations.

    This protocol defines the contract that all chat platform adapters
    (Slack, Discord, Teams, etc.) must implement.
    """

    async def connect(self) -> None:
        """
        Establish connection to the chat platform.

        This method should set up the necessary connections and
        authenticate with the chat service.

        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If credentials are invalid
        """
        ...

    async def disconnect(self) -> None:
        """
        Gracefully close the connection.

        This method should clean up resources and close connections
        to the chat platform.
        """
        ...

    async def listen(self) -> AsyncIterator[ChatMessage]:
        """
        Yield incoming messages from monitored channels.

        This is an async generator that yields messages as they arrive.
        It should handle reconnection internally on transient failures.

        Yields:
            ChatMessage: Each incoming message from monitored channels

        Example:
            async for message in provider.listen():
                # Process message
                pass
        """
        ...

    async def send_reply(
        self,
        channel_id: str,
        text: str,
        thread_id: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Send a reply to a channel, optionally in a thread.

        Args:
            channel_id: Target channel identifier
            text: Plain text message (fallback for rich formatting)
            thread_id: Parent message ID for threading (optional)
            blocks: Optional rich content blocks (platform-specific)

        Returns:
            Message ID of the sent message

        Raises:
            SendError: If message delivery fails
        """
        ...

    async def add_reaction(
        self,
        channel_id: str,
        message_id: str,
        reaction: str,
    ) -> None:
        """
        Add a reaction/emoji to a message.

        Used to acknowledge receipt (e.g., :eyes: when processing starts).

        Args:
            channel_id: Channel containing the message
            message_id: Target message identifier
            reaction: Reaction name (without colons, e.g., "eyes")

        Raises:
            ReactionError: If adding reaction fails
        """
        ...

    async def remove_reaction(
        self,
        channel_id: str,
        message_id: str,
        reaction: str,
    ) -> None:
        """
        Remove a previously added reaction.

        Args:
            channel_id: Channel containing the message
            message_id: Target message identifier
            reaction: Reaction name (without colons, e.g., "eyes")

        Raises:
            ReactionError: If removing reaction fails
        """
        ...
