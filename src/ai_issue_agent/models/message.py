"""Data models for chat messages."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class ChatMessage:
    """An incoming message from a chat platform."""

    channel_id: str
    message_id: str
    thread_id: str | None  # None if not in a thread
    user_id: str
    user_name: str
    text: str
    timestamp: datetime

    # Platform-specific metadata
    raw_event: dict[str, Any]  # Original event payload


@dataclass(frozen=True)
class ChatReply:
    """A reply to send to chat."""

    channel_id: str
    text: str
    thread_id: str | None = None
    blocks: list[dict[str, Any]] | None = None  # Rich formatting


class ProcessingResult(Enum):
    """Outcome of processing a message."""

    NO_TRACEBACK = "no_traceback"
    EXISTING_ISSUE_LINKED = "existing_issue_linked"
    NEW_ISSUE_CREATED = "new_issue_created"
    ERROR = "error"
