"""Message processing pipeline orchestrator.

This module implements the MessageHandler class that coordinates the full
message processing pipeline:
1. Acknowledge message with reaction
2. Check for traceback
3. Parse traceback
4. Search for existing issues
5. Either link to existing or create new issue
6. Update reaction to completion status

See docs/ARCHITECTURE.md for the canonical design.
"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING

import structlog

from ai_issue_agent.config.schema import AgentConfig
from ai_issue_agent.core.code_analyzer import CodeAnalyzer
from ai_issue_agent.core.issue_matcher import IssueMatcher
from ai_issue_agent.models.issue import IssueCreate
from ai_issue_agent.models.message import ChatMessage, ProcessingResult

if TYPE_CHECKING:
    from ai_issue_agent.core.traceback_parser import TracebackParser
    from ai_issue_agent.interfaces.chat import ChatProvider
    from ai_issue_agent.interfaces.llm import LLMProvider
    from ai_issue_agent.interfaces.vcs import VCSProvider
    from ai_issue_agent.models.issue import Issue

log = structlog.get_logger()


class MessageHandlerError(Exception):
    """Base exception for message handler errors."""


class MessageHandler:
    """Orchestrates the message processing pipeline.

    Responsibilities:
    - Coordinate traceback parsing, issue matching, and analysis
    - Decide whether to link existing or create new issue
    - Format and send replies
    - Track processing state for observability

    The pipeline follows this flow:
    1. Add 👀 reaction (acknowledge receipt)
    2. Check for traceback (TracebackParser.contains_traceback())
    3. If no traceback: remove reaction, return NO_TRACEBACK
    4. Parse traceback
    5. Identify repository (from config/channel mapping)
    6. Search existing issues (IssueMatcher.find_matches())
    7. If high-confidence match: reply with link, return EXISTING_ISSUE_LINKED
    8. If no match: clone repo, extract code context
    9. Analyze error with LLM
    10. Generate issue title and body
    11. Create GitHub issue
    12. Reply with new issue link
    13. Update reaction to ✅
    14. Return NEW_ISSUE_CREATED

    Example:
        handler = MessageHandler(chat, vcs, llm, parser, matcher, analyzer, config)
        result = await handler.handle(message)
    """

    # Default reactions (can be overridden by config)
    DEFAULT_PROCESSING_REACTION = "eyes"
    DEFAULT_COMPLETE_REACTION = "white_check_mark"
    DEFAULT_ERROR_REACTION = "x"

    def __init__(
        self,
        chat: ChatProvider,
        vcs: VCSProvider,
        llm: LLMProvider,
        parser: TracebackParser,
        matcher: IssueMatcher,
        analyzer: CodeAnalyzer,
        config: AgentConfig,
    ) -> None:
        """Initialize the MessageHandler.

        Args:
            chat: Chat provider for sending replies and reactions
            vcs: VCS provider for issue operations
            llm: LLM provider for error analysis
            parser: TracebackParser for detecting and parsing tracebacks
            matcher: IssueMatcher for finding existing issues
            analyzer: CodeAnalyzer for extracting code context
            config: Agent configuration
        """
        self._chat = chat
        self._vcs = vcs
        self._llm = llm
        self._parser = parser
        self._matcher = matcher
        self._analyzer = analyzer
        self._config = config

        # Get reactions from config if available
        if config.chat.slack:
            self._processing_reaction = config.chat.slack.processing_reaction
            self._complete_reaction = config.chat.slack.complete_reaction
            self._error_reaction = config.chat.slack.error_reaction
        else:
            self._processing_reaction = self.DEFAULT_PROCESSING_REACTION
            self._complete_reaction = self.DEFAULT_COMPLETE_REACTION
            self._error_reaction = self.DEFAULT_ERROR_REACTION

    async def handle(self, message: ChatMessage) -> ProcessingResult:
        """Process a message through the full pipeline.

        Args:
            message: Incoming chat message to process

        Returns:
            ProcessingResult indicating what action was taken
        """
        start_time = time.time()
        channel_id = message.channel_id
        message_id = message.message_id
        thread_id = message.thread_id or message_id  # Reply in thread

        log.info(
            "processing_message",
            channel_id=channel_id,
            message_id=message_id,
            user=message.user_name,
        )

        try:
            # Step 1: Add processing reaction
            await self._add_reaction(channel_id, message_id, self._processing_reaction)

            # Step 2: Check for traceback
            if not self._parser.contains_traceback(message.text):
                log.debug("no_traceback_found", message_id=message_id)
                await self._remove_reaction(channel_id, message_id, self._processing_reaction)
                return ProcessingResult.NO_TRACEBACK

            # Step 3: Parse traceback
            try:
                traceback = self._parser.parse(message.text)
            except Exception as e:
                log.warning("traceback_parse_failed", message_id=message_id, error=str(e))
                await self._remove_reaction(channel_id, message_id, self._processing_reaction)
                return ProcessingResult.NO_TRACEBACK

            log.info(
                "traceback_parsed",
                exception_type=traceback.exception_type,
                frames_count=len(traceback.frames),
            )

            # Step 4: Identify repository
            repo = self._get_repository_for_channel(channel_id)
            if not repo:
                log.warning("no_repository_mapped", channel_id=channel_id)
                await self._send_error_reply(
                    channel_id,
                    thread_id,
                    "No repository configured for this channel.",
                )
                await self._update_reaction(
                    channel_id,
                    message_id,
                    self._processing_reaction,
                    self._error_reaction,
                )
                return ProcessingResult.ERROR

            # Step 5: Search for existing issues
            matches = await self._matcher.find_matches(repo, traceback)

            # Step 6: Check for high-confidence match
            if matches and matches[0].confidence >= self._config.matching.confidence_threshold:
                best_match = matches[0]
                log.info(
                    "existing_issue_found",
                    issue_number=best_match.issue.number,
                    confidence=best_match.confidence,
                )

                # Reply with link to existing issue
                await self._send_existing_issue_reply(
                    channel_id,
                    thread_id,
                    best_match.issue,
                    best_match.confidence,
                )
                await self._update_reaction(
                    channel_id,
                    message_id,
                    self._processing_reaction,
                    self._complete_reaction,
                )

                self._log_completion(start_time, ProcessingResult.EXISTING_ISSUE_LINKED)
                return ProcessingResult.EXISTING_ISSUE_LINKED

            # Step 7: Clone repo and extract code context
            log.info("no_matching_issue_found", creating_new=True)
            code_contexts = await self._analyzer.analyze(repo, traceback)

            # Step 8: Analyze error with LLM
            analysis = await self._llm.analyze_error(
                traceback=traceback,
                code_context=code_contexts,
            )

            # Step 9: Generate issue title and body
            title = await self._llm.generate_issue_title(traceback, analysis)
            body = await self._llm.generate_issue_body(traceback, analysis, code_contexts)

            # Step 10: Create the issue
            issue_create = IssueCreate(
                title=title,
                body=body,
                labels=tuple(self._get_default_labels()),
            )
            created_issue = await self._vcs.create_issue(repo, issue_create)

            log.info(
                "issue_created",
                issue_number=created_issue.number,
                issue_url=created_issue.url,
            )

            # Step 11: Reply with new issue link
            await self._send_new_issue_reply(channel_id, thread_id, created_issue)

            # Step 12: Update reaction to complete
            await self._update_reaction(
                channel_id,
                message_id,
                self._processing_reaction,
                self._complete_reaction,
            )

            self._log_completion(start_time, ProcessingResult.NEW_ISSUE_CREATED)
            return ProcessingResult.NEW_ISSUE_CREATED

        except Exception as e:
            log.exception("message_processing_failed", error=str(e))

            # Send error reply
            await self._send_error_reply(
                channel_id,
                thread_id,
                "An error occurred while processing this traceback. Please try again later.",
            )

            # Update reaction to error (best effort)
            with contextlib.suppress(Exception):
                await self._update_reaction(
                    channel_id,
                    message_id,
                    self._processing_reaction,
                    self._error_reaction,
                )

            return ProcessingResult.ERROR

    def _get_repository_for_channel(self, channel_id: str) -> str | None:
        """Get the repository mapped to a channel.

        Args:
            channel_id: Chat channel identifier

        Returns:
            Repository identifier or None if not mapped
        """
        # Check channel_repos mapping first
        if channel_id in self._config.vcs.channel_repos:
            return self._config.vcs.channel_repos[channel_id]

        # Fall back to default repo
        if self._config.vcs.github:
            return self._config.vcs.github.default_repo

        return None

    def _get_default_labels(self) -> list[str]:
        """Get default labels for new issues."""
        if self._config.vcs.github:
            return self._config.vcs.github.default_labels
        return ["auto-triaged"]

    async def _add_reaction(
        self,
        channel_id: str,
        message_id: str,
        reaction: str,
    ) -> None:
        """Add a reaction to a message (with error handling)."""
        try:
            await self._chat.add_reaction(channel_id, message_id, reaction)
        except Exception as e:
            log.warning("add_reaction_failed", reaction=reaction, error=str(e))

    async def _remove_reaction(
        self,
        channel_id: str,
        message_id: str,
        reaction: str,
    ) -> None:
        """Remove a reaction from a message (with error handling)."""
        try:
            await self._chat.remove_reaction(channel_id, message_id, reaction)
        except Exception as e:
            log.warning("remove_reaction_failed", reaction=reaction, error=str(e))

    async def _update_reaction(
        self,
        channel_id: str,
        message_id: str,
        old_reaction: str,
        new_reaction: str,
    ) -> None:
        """Update a reaction on a message (remove old, add new)."""
        await self._remove_reaction(channel_id, message_id, old_reaction)
        await self._add_reaction(channel_id, message_id, new_reaction)

    async def _send_existing_issue_reply(
        self,
        channel_id: str,
        thread_id: str,
        issue: Issue,
        confidence: float,
    ) -> None:
        """Send a reply linking to an existing issue.

        Args:
            channel_id: Target channel
            thread_id: Thread to reply in
            issue: The matched issue
            confidence: Match confidence score
        """

        confidence_pct = int(confidence * 100)
        text = (
            f"🔗 This error appears to match an existing issue "
            f"(confidence: {confidence_pct}%):\n\n"
            f"*<{issue.url}|#{issue.number}: {issue.title}>*\n\n"
            f"State: {issue.state.value}"
        )

        try:
            await self._chat.send_reply(
                channel_id=channel_id,
                text=text,
                thread_id=thread_id,
            )
        except Exception as e:
            log.error("send_reply_failed", error=str(e))

    async def _send_new_issue_reply(
        self,
        channel_id: str,
        thread_id: str,
        issue: Issue,
    ) -> None:
        """Send a reply with the newly created issue.

        Args:
            channel_id: Target channel
            thread_id: Thread to reply in
            issue: The created issue
        """

        text = (
            f"📝 I've created a new issue for this error:\n\n"
            f"*<{issue.url}|#{issue.number}: {issue.title}>*"
        )

        try:
            await self._chat.send_reply(
                channel_id=channel_id,
                text=text,
                thread_id=thread_id,
            )
        except Exception as e:
            log.error("send_reply_failed", error=str(e))

    async def _send_error_reply(
        self,
        channel_id: str,
        thread_id: str,
        message: str,
    ) -> None:
        """Send an error reply to the user.

        Args:
            channel_id: Target channel
            thread_id: Thread to reply in
            message: Error message to display
        """
        text = f"⚠️ {message}"

        try:
            await self._chat.send_reply(
                channel_id=channel_id,
                text=text,
                thread_id=thread_id,
            )
        except Exception as e:
            log.error("send_error_reply_failed", error=str(e))

    def _log_completion(self, start_time: float, result: ProcessingResult) -> None:
        """Log completion statistics.

        Args:
            start_time: Time when processing started
            result: Processing result
        """
        duration = time.time() - start_time
        log.info(
            "message_processing_complete",
            result=result.value,
            duration_seconds=round(duration, 2),
        )
