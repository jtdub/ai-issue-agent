"""Main Agent orchestrator that coordinates all components.

This module implements the Agent class that serves as the main entry point
for the AI Issue Agent. It:
- Manages adapter lifecycle (initialize, connect, disconnect)
- Coordinates message processing with concurrency control
- Handles graceful shutdown on signals (SIGTERM, SIGINT)
- Provides observability through structured logging

See docs/ARCHITECTURE.md for the canonical design.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from typing import TYPE_CHECKING

import structlog

from ai_issue_agent.config.schema import AgentConfig
from ai_issue_agent.core.code_analyzer import CodeAnalyzer
from ai_issue_agent.core.issue_matcher import IssueMatcher
from ai_issue_agent.core.message_handler import MessageHandler
from ai_issue_agent.models.message import ChatMessage, ProcessingResult

if TYPE_CHECKING:
    from ai_issue_agent.core.traceback_parser import TracebackParser
    from ai_issue_agent.interfaces.chat import ChatProvider
    from ai_issue_agent.interfaces.llm import LLMProvider
    from ai_issue_agent.interfaces.vcs import VCSProvider

log = structlog.get_logger()


class AgentError(Exception):
    """Base exception for agent errors."""


class StartupError(AgentError):
    """Failed to start the agent."""


class ShutdownError(AgentError):
    """Error during shutdown."""


class Agent:
    """Main orchestrator that coordinates all components.

    Responsibilities:
    - Initialize and manage adapter instances
    - Route incoming messages through the processing pipeline
    - Handle graceful startup and shutdown
    - Manage concurrent message processing

    The agent uses asyncio.Semaphore to limit concurrent message processing
    to the configured max_concurrent limit.

    Example:
        agent = Agent(config, chat, vcs, llm, parser)
        await agent.start()  # Blocks until shutdown signal

        # Or manual control:
        await agent.start()
        # ... do other things ...
        await agent.stop()
    """

    # Default configuration values
    DEFAULT_MAX_CONCURRENT = 5
    DEFAULT_SHUTDOWN_TIMEOUT = 30

    def __init__(
        self,
        config: AgentConfig,
        chat: ChatProvider,
        vcs: VCSProvider,
        llm: LLMProvider,
        parser: TracebackParser,
    ) -> None:
        """Initialize the Agent.

        Args:
            config: Application configuration
            chat: Chat provider adapter
            vcs: VCS provider adapter
            llm: LLM provider adapter
            parser: TracebackParser instance
        """
        self._config = config
        self._chat = chat
        self._vcs = vcs
        self._llm = llm
        self._parser = parser

        # Initialize core components
        self._matcher = IssueMatcher(vcs, llm, config.matching)
        self._analyzer = CodeAnalyzer(
            vcs,
            config.analysis,
            config.vcs.github,
        )
        self._handler = MessageHandler(
            chat,
            vcs,
            llm,
            parser,
            self._matcher,
            self._analyzer,
            config,
        )

        # Concurrency control
        self._max_concurrent = self.DEFAULT_MAX_CONCURRENT
        self._semaphore: asyncio.Semaphore | None = None
        self._active_tasks: set[asyncio.Task[ProcessingResult]] = set()

        # Lifecycle state
        self._running = False
        self._shutdown_event: asyncio.Event | None = None
        self._listen_task: asyncio.Task[None] | None = None

        # Statistics
        self._messages_processed = 0
        self._errors_count = 0

    @property
    def is_running(self) -> bool:
        """Return True if the agent is currently running."""
        return self._running

    @property
    def stats(self) -> dict[str, int]:
        """Return processing statistics."""
        return {
            "messages_processed": self._messages_processed,
            "errors_count": self._errors_count,
            "active_tasks": len(self._active_tasks),
        }

    async def start(self) -> None:
        """Start the agent and begin processing messages.

        This method:
        1. Initializes all adapters
        2. Connects to the chat provider
        3. Sets up signal handlers
        4. Starts the message listening loop
        5. Blocks until shutdown is triggered

        Raises:
            StartupError: If startup fails
        """
        if self._running:
            log.warning("agent_already_running")
            return

        log.info("agent_starting", config=self._config.model_dump(exclude={"chat", "llm", "vcs"}))

        try:
            # Initialize concurrency control
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
            self._shutdown_event = asyncio.Event()

            # Connect to chat provider
            log.info("connecting_to_chat_provider")
            await self._chat.connect()
            log.info("chat_provider_connected")

            # Set up signal handlers
            self._setup_signal_handlers()

            # Mark as running
            self._running = True
            log.info("agent_started")

            # Start listening for messages
            await self._listen_for_messages()

        except Exception as e:
            log.exception("agent_startup_failed", error=str(e))
            await self._cleanup()
            raise StartupError(f"Failed to start agent: {e}") from e

    async def stop(self) -> None:
        """Gracefully stop the agent.

        This method:
        1. Signals shutdown to all components
        2. Waits for in-flight requests to complete (with timeout)
        3. Disconnects from chat provider
        4. Cleans up resources
        """
        if not self._running:
            log.warning("agent_not_running")
            return

        log.info("agent_stopping", active_tasks=len(self._active_tasks))

        # Signal shutdown
        if self._shutdown_event:
            self._shutdown_event.set()

        # Wait for in-flight tasks with timeout
        await self._wait_for_tasks()

        # Cleanup
        await self._cleanup()

        self._running = False
        log.info(
            "agent_stopped",
            messages_processed=self._messages_processed,
            errors=self._errors_count,
        )

    async def process_message(self, message: ChatMessage) -> ProcessingResult:
        """Process a single message through the pipeline.

        This method respects the concurrency limit and handles errors
        gracefully.

        Args:
            message: Message to process

        Returns:
            ProcessingResult indicating what action was taken
        """
        if not self._semaphore:
            return ProcessingResult.ERROR

        async with self._semaphore:
            try:
                result = await self._handler.handle(message)
                self._messages_processed += 1

                if result == ProcessingResult.ERROR:
                    self._errors_count += 1

                return result

            except Exception as e:
                log.exception(
                    "message_processing_error",
                    message_id=message.message_id,
                    error=str(e),
                )
                self._errors_count += 1
                return ProcessingResult.ERROR

    async def _listen_for_messages(self) -> None:
        """Listen for incoming messages and process them.

        This method runs until shutdown is triggered.
        """
        log.info("starting_message_listener")

        try:
            async for message in self._chat.listen():
                # Check for shutdown
                if self._shutdown_event and self._shutdown_event.is_set():
                    log.info("shutdown_signal_received_stopping_listener")
                    break

                # Create task for processing
                task = asyncio.create_task(
                    self.process_message(message),
                    name=f"process_{message.message_id}",
                )
                self._active_tasks.add(task)
                task.add_done_callback(self._active_tasks.discard)

        except asyncio.CancelledError:
            log.info("message_listener_cancelled")
        except Exception as e:
            log.exception("message_listener_error", error=str(e))
            raise

    async def _wait_for_tasks(self) -> None:
        """Wait for active tasks to complete with timeout."""
        if not self._active_tasks:
            return

        log.info("waiting_for_active_tasks", count=len(self._active_tasks))

        try:
            # Wait with timeout
            done, pending = await asyncio.wait(
                self._active_tasks,
                timeout=self.DEFAULT_SHUTDOWN_TIMEOUT,
            )

            if pending:
                log.warning(
                    "cancelling_pending_tasks",
                    count=len(pending),
                )
                for task in pending:
                    task.cancel()

                # Wait briefly for cancellation
                await asyncio.gather(*pending, return_exceptions=True)

            log.info(
                "tasks_completed",
                completed=len(done),
                cancelled=len(pending),
            )

        except Exception as e:
            log.error("wait_for_tasks_error", error=str(e))

    async def _cleanup(self) -> None:
        """Clean up resources."""
        log.debug("cleaning_up_resources")

        # Cancel listen task if running
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listen_task

        # Disconnect from chat
        try:
            await self._chat.disconnect()
            log.info("chat_provider_disconnected")
        except Exception as e:
            log.warning("chat_disconnect_error", error=str(e))

        # Clear active tasks
        self._active_tasks.clear()

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda s: asyncio.create_task(self._handle_signal(s)),
                sig,
            )
            log.debug("signal_handler_registered", signal=sig.name)

    async def _handle_signal(self, sig: signal.Signals) -> None:
        """Handle shutdown signal.

        Args:
            sig: Signal that was received
        """
        log.info("received_signal", signal=sig.name)
        await self.stop()


async def create_agent(config: AgentConfig) -> Agent:
    """Factory function to create an Agent with all dependencies.

    This function instantiates the appropriate adapters based on
    the configuration and creates an Agent instance.

    Args:
        config: Application configuration

    Returns:
        Configured Agent instance

    Raises:
        ValueError: If configuration is invalid
    """
    # Import TracebackParser here to avoid circular imports
    from ai_issue_agent.core.traceback_parser import TracebackParser

    # Create adapters based on configuration
    chat = await _create_chat_adapter(config)
    vcs = await _create_vcs_adapter(config)
    llm = await _create_llm_adapter(config)
    parser = TracebackParser()

    return Agent(config, chat, vcs, llm, parser)


async def _create_chat_adapter(config: AgentConfig) -> ChatProvider:
    """Create a chat adapter based on configuration.

    Args:
        config: Application configuration

    Returns:
        Chat provider instance

    Raises:
        ValueError: If provider is not supported
    """
    provider = config.chat.provider

    if provider == "slack":
        if not config.chat.slack:
            raise ValueError("Slack configuration required when provider is 'slack'")
        # Import here to avoid loading unnecessary dependencies
        from ai_issue_agent.adapters.chat.slack import SlackAdapter

        return SlackAdapter(config.chat.slack)

    raise ValueError(f"Unsupported chat provider: {provider}")


async def _create_vcs_adapter(config: AgentConfig) -> VCSProvider:
    """Create a VCS adapter based on configuration.

    Args:
        config: Application configuration

    Returns:
        VCS provider instance

    Raises:
        ValueError: If provider is not supported
    """
    provider = config.vcs.provider

    if provider == "github":
        if not config.vcs.github:
            raise ValueError("GitHub configuration required when provider is 'github'")
        from ai_issue_agent.adapters.vcs.github import GitHubAdapter

        return GitHubAdapter(config.vcs.github)

    raise ValueError(f"Unsupported VCS provider: {provider}")


async def _create_llm_adapter(config: AgentConfig) -> LLMProvider:
    """Create an LLM adapter based on configuration.

    Args:
        config: Application configuration

    Returns:
        LLM provider instance

    Raises:
        ValueError: If provider is not supported
    """
    provider = config.llm.provider

    if provider == "openai":
        if not config.llm.openai:
            raise ValueError("OpenAI configuration required when provider is 'openai'")
        from ai_issue_agent.adapters.llm.openai import (  # type: ignore[import-not-found]
            OpenAIAdapter,
        )

        return OpenAIAdapter(config.llm.openai)  # type: ignore[no-any-return]

    if provider == "anthropic":
        if not config.llm.anthropic:
            raise ValueError("Anthropic configuration required when provider is 'anthropic'")
        from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

        return AnthropicAdapter(config.llm.anthropic)

    if provider == "ollama":
        if not config.llm.ollama:
            raise ValueError("Ollama configuration required when provider is 'ollama'")
        from ai_issue_agent.adapters.llm.ollama import (  # type: ignore[import-not-found]
            OllamaAdapter,
        )

        return OllamaAdapter(config.llm.ollama)  # type: ignore[no-any-return]

    raise ValueError(f"Unsupported LLM provider: {provider}")
