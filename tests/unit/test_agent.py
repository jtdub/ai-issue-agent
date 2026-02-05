"""Tests for Agent orchestrator functionality."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_issue_agent.config.schema import (
    AgentConfig,
    AnalysisConfig,
    ChatConfig,
    GitHubConfig,
    LLMConfig,
    MatchingConfig,
    OpenAIConfig,
    SlackConfig,
    VCSConfig,
)
from ai_issue_agent.core.agent import Agent
from ai_issue_agent.models.message import ChatMessage, ProcessingResult


@pytest.fixture
def agent_config() -> AgentConfig:
    """Create a test agent configuration."""
    return AgentConfig(
        chat=ChatConfig(
            provider="slack",
            slack=SlackConfig(
                bot_token="xoxb-test-token",
                app_token="xapp-test-token",
                channels=["C123456"],
            ),
        ),
        vcs=VCSConfig(
            provider="github",
            github=GitHubConfig(
                default_repo="owner/repo",
            ),
        ),
        llm=LLMConfig(
            provider="openai",
            openai=OpenAIConfig(api_key="sk-test-key"),
        ),
        matching=MatchingConfig(
            confidence_threshold=0.85,
            max_search_results=20,
            include_closed=True,
            search_cache_ttl=300,
        ),
        analysis=AnalysisConfig(
            context_lines=15,
            max_files=10,
        ),
    )


@pytest.fixture
def mock_chat() -> AsyncMock:
    """Create a mock chat provider."""
    mock = AsyncMock()
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()

    # Create an async generator for listen
    async def mock_listen() -> AsyncIterator[ChatMessage]:
        # Yield one message then stop
        yield ChatMessage(
            channel_id="C123",
            message_id="M123",
            thread_id=None,
            user_id="U123",
            user_name="test",
            text="test message",
            timestamp=datetime.now(),
            raw_event={},
        )
        # Then wait indefinitely (will be cancelled on shutdown)
        await asyncio.sleep(1000)

    mock.listen = mock_listen
    return mock


@pytest.fixture
def mock_vcs() -> AsyncMock:
    """Create a mock VCS provider."""
    return AsyncMock()


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Create a mock LLM provider."""
    return AsyncMock()


@pytest.fixture
def mock_parser() -> MagicMock:
    """Create a mock traceback parser."""
    mock = MagicMock()
    mock.contains_traceback.return_value = False
    return mock


@pytest.fixture
def agent(
    agent_config: AgentConfig,
    mock_chat: AsyncMock,
    mock_vcs: AsyncMock,
    mock_llm: AsyncMock,
    mock_parser: MagicMock,
) -> Agent:
    """Create an Agent instance for testing."""
    return Agent(
        config=agent_config,
        chat=mock_chat,
        vcs=mock_vcs,
        llm=mock_llm,
        parser=mock_parser,
    )


class TestAgent:
    """Tests for Agent class."""

    def test_init(
        self,
        agent: Agent,
        agent_config: AgentConfig,
    ) -> None:
        """Test Agent initialization."""
        assert agent._config == agent_config
        assert agent.is_running is False
        assert agent.stats["messages_processed"] == 0
        assert agent.stats["errors_count"] == 0

    def test_is_running_property(self, agent: Agent) -> None:
        """Test is_running property."""
        assert agent.is_running is False
        agent._running = True
        assert agent.is_running is True

    def test_stats_property(self, agent: Agent) -> None:
        """Test stats property."""
        stats = agent.stats

        assert "messages_processed" in stats
        assert "errors_count" in stats
        assert "active_tasks" in stats
        assert stats["messages_processed"] == 0

    @pytest.mark.asyncio
    async def test_start_connects_to_chat(
        self,
        agent: Agent,
        mock_chat: AsyncMock,
    ) -> None:
        """Test that start connects to chat provider."""
        # Start agent in background
        start_task = asyncio.create_task(agent.start())

        # Give it time to connect
        await asyncio.sleep(0.1)

        mock_chat.connect.assert_called_once()

        # Stop the agent
        await agent.stop()
        start_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await start_task

    @pytest.mark.asyncio
    async def test_start_when_already_running(
        self,
        agent: Agent,
    ) -> None:
        """Test starting agent that's already running."""
        agent._running = True

        # Should return immediately without error
        await agent.start()

        # Still running
        assert agent._running is True

    @pytest.mark.asyncio
    async def test_stop_disconnects_from_chat(
        self,
        agent: Agent,
        mock_chat: AsyncMock,
    ) -> None:
        """Test that stop disconnects from chat provider."""
        # Simulate running state
        agent._running = True
        agent._shutdown_event = asyncio.Event()
        agent._semaphore = asyncio.Semaphore(5)

        await agent.stop()

        mock_chat.disconnect.assert_called_once()
        assert agent._running is False

    @pytest.mark.asyncio
    async def test_stop_when_not_running(
        self,
        agent: Agent,
        mock_chat: AsyncMock,
    ) -> None:
        """Test stopping agent that's not running."""
        await agent.stop()

        # disconnect should not be called if not running
        mock_chat.disconnect.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_no_traceback(
        self,
        agent: Agent,
        mock_parser: MagicMock,
    ) -> None:
        """Test processing message with no traceback."""
        agent._semaphore = asyncio.Semaphore(5)
        mock_parser.contains_traceback.return_value = False

        message = ChatMessage(
            channel_id="C123",
            message_id="M123",
            thread_id=None,
            user_id="U123",
            user_name="test",
            text="Just a normal message",
            timestamp=datetime.now(),
            raw_event={},
        )

        result = await agent.process_message(message)

        assert result == ProcessingResult.NO_TRACEBACK
        assert agent._messages_processed == 1

    @pytest.mark.asyncio
    async def test_process_message_increments_stats(
        self,
        agent: Agent,
        mock_parser: MagicMock,
    ) -> None:
        """Test that processing increments statistics."""
        agent._semaphore = asyncio.Semaphore(5)
        mock_parser.contains_traceback.return_value = False

        message = ChatMessage(
            channel_id="C123",
            message_id="M123",
            thread_id=None,
            user_id="U123",
            user_name="test",
            text="test",
            timestamp=datetime.now(),
            raw_event={},
        )

        await agent.process_message(message)
        await agent.process_message(message)

        assert agent._messages_processed == 2

    @pytest.mark.asyncio
    async def test_process_message_without_semaphore(
        self,
        agent: Agent,
    ) -> None:
        """Test processing message without initialized semaphore."""
        # Semaphore not set
        agent._semaphore = None

        message = ChatMessage(
            channel_id="C123",
            message_id="M123",
            thread_id=None,
            user_id="U123",
            user_name="test",
            text="test",
            timestamp=datetime.now(),
            raw_event={},
        )

        result = await agent.process_message(message)

        assert result == ProcessingResult.ERROR

    @pytest.mark.asyncio
    async def test_process_message_error_increments_error_count(
        self,
        agent: Agent,
        mock_parser: MagicMock,
    ) -> None:
        """Test that errors increment error count."""
        agent._semaphore = asyncio.Semaphore(5)
        mock_parser.contains_traceback.side_effect = Exception("Test error")

        message = ChatMessage(
            channel_id="C123",
            message_id="M123",
            thread_id=None,
            user_id="U123",
            user_name="test",
            text="test",
            timestamp=datetime.now(),
            raw_event={},
        )

        result = await agent.process_message(message)

        assert result == ProcessingResult.ERROR
        assert agent._errors_count == 1

    @pytest.mark.asyncio
    async def test_wait_for_tasks_empty(self, agent: Agent) -> None:
        """Test waiting for tasks when none are active."""
        agent._active_tasks = set()

        # Should complete immediately
        await agent._wait_for_tasks()

    @pytest.mark.asyncio
    async def test_wait_for_tasks_with_pending(self, agent: Agent) -> None:
        """Test waiting for pending tasks."""

        # Create a task that completes quickly
        async def quick_task() -> ProcessingResult:
            await asyncio.sleep(0.01)
            return ProcessingResult.NO_TRACEBACK

        task = asyncio.create_task(quick_task())
        agent._active_tasks = {task}

        await agent._wait_for_tasks()

        assert task.done()

    @pytest.mark.asyncio
    async def test_cleanup_cancels_listen_task(
        self,
        agent: Agent,
        mock_chat: AsyncMock,
    ) -> None:
        """Test that cleanup cancels the listen task."""

        # Create a running listen task
        async def long_running() -> None:
            await asyncio.sleep(1000)

        agent._listen_task = asyncio.create_task(long_running())

        await agent._cleanup()

        assert agent._listen_task.cancelled() or agent._listen_task.done()

    @pytest.mark.asyncio
    async def test_cleanup_handles_disconnect_error(
        self,
        agent: Agent,
        mock_chat: AsyncMock,
    ) -> None:
        """Test cleanup handles disconnect errors gracefully."""
        mock_chat.disconnect.side_effect = Exception("Disconnect error")

        # Should not raise
        await agent._cleanup()

    def test_setup_signal_handlers(self, agent: Agent) -> None:
        """Test signal handler setup."""
        # This test verifies the method doesn't raise
        # We can't easily test the actual signal handling
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Run setup in the loop context
            async def setup() -> None:
                agent._setup_signal_handlers()

            loop.run_until_complete(setup())
        finally:
            loop.close()
            asyncio.set_event_loop(None)


class TestAgentConcurrency:
    """Tests for Agent concurrency handling."""

    @pytest.mark.asyncio
    async def test_concurrent_message_processing(
        self,
        agent_config: AgentConfig,
        mock_chat: AsyncMock,
        mock_vcs: AsyncMock,
        mock_llm: AsyncMock,
        mock_parser: MagicMock,
    ) -> None:
        """Test that messages are processed concurrently."""
        agent = Agent(agent_config, mock_chat, mock_vcs, mock_llm, mock_parser)
        agent._semaphore = asyncio.Semaphore(5)
        mock_parser.contains_traceback.return_value = False

        messages = [
            ChatMessage(
                channel_id="C123",
                message_id=f"M{i}",
                thread_id=None,
                user_id="U123",
                user_name="test",
                text="test",
                timestamp=datetime.now(),
                raw_event={},
            )
            for i in range(3)
        ]

        # Process all messages concurrently
        results = await asyncio.gather(*[agent.process_message(msg) for msg in messages])

        assert all(r == ProcessingResult.NO_TRACEBACK for r in results)
        assert agent._messages_processed == 3

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(
        self,
        agent_config: AgentConfig,
        mock_chat: AsyncMock,
        mock_vcs: AsyncMock,
        mock_llm: AsyncMock,
        mock_parser: MagicMock,
    ) -> None:
        """Test that semaphore limits concurrent processing."""
        agent = Agent(agent_config, mock_chat, mock_vcs, mock_llm, mock_parser)
        agent._semaphore = asyncio.Semaphore(1)  # Only 1 at a time

        processing_count = 0
        max_concurrent = 0

        # Mock the handler's handle method to introduce async delay
        async def slow_handle(message: ChatMessage) -> ProcessingResult:
            nonlocal processing_count, max_concurrent
            processing_count += 1
            max_concurrent = max(max_concurrent, processing_count)
            await asyncio.sleep(0.05)
            processing_count -= 1
            return ProcessingResult.NO_TRACEBACK

        with patch.object(agent._handler, "handle", slow_handle):
            messages = [
                ChatMessage(
                    channel_id="C123",
                    message_id=f"M{i}",
                    thread_id=None,
                    user_id="U123",
                    user_name="test",
                    text="test",
                    timestamp=datetime.now(),
                    raw_event={},
                )
                for i in range(3)
            ]

            await asyncio.gather(*[agent.process_message(msg) for msg in messages])

        # With semaphore=1, max concurrent should be 1
        assert max_concurrent == 1


class TestAgentFactory:
    """Tests for agent factory function."""

    @pytest.mark.asyncio
    async def test_create_agent_unsupported_chat_provider(self) -> None:
        """Test factory with unsupported chat provider."""
        from ai_issue_agent.core.agent import _create_chat_adapter

        config = AgentConfig(
            chat=ChatConfig(provider="discord"),  # Not implemented
            vcs=VCSConfig(provider="github", github=GitHubConfig(default_repo="owner/repo")),
            llm=LLMConfig(provider="openai", openai=OpenAIConfig(api_key="sk-test")),
        )

        with pytest.raises(ValueError) as exc_info:
            await _create_chat_adapter(config)

        assert "Unsupported chat provider" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_agent_missing_slack_config(self) -> None:
        """Test factory with Slack provider but no config."""
        from ai_issue_agent.core.agent import _create_chat_adapter

        config = AgentConfig(
            chat=ChatConfig(provider="slack", slack=None),
            vcs=VCSConfig(provider="github", github=GitHubConfig(default_repo="owner/repo")),
            llm=LLMConfig(provider="openai", openai=OpenAIConfig(api_key="sk-test")),
        )

        with pytest.raises(ValueError) as exc_info:
            await _create_chat_adapter(config)

        assert "Slack configuration required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_vcs_adapter_unsupported(self) -> None:
        """Test VCS adapter factory with unsupported provider."""
        from ai_issue_agent.core.agent import _create_vcs_adapter

        config = AgentConfig(
            chat=ChatConfig(
                provider="slack",
                slack=SlackConfig(bot_token="xoxb-test", app_token="xapp-test"),
            ),
            vcs=VCSConfig(provider="gitlab"),  # Not implemented
            llm=LLMConfig(provider="openai", openai=OpenAIConfig(api_key="sk-test")),
        )

        with pytest.raises(ValueError) as exc_info:
            await _create_vcs_adapter(config)

        assert "Unsupported VCS provider" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_llm_adapter_unsupported(self) -> None:
        """Test LLM adapter factory with unsupported provider."""
        from ai_issue_agent.core.agent import _create_llm_adapter

        config = AgentConfig(
            chat=ChatConfig(
                provider="slack",
                slack=SlackConfig(bot_token="xoxb-test", app_token="xapp-test"),
            ),
            vcs=VCSConfig(provider="github", github=GitHubConfig(default_repo="owner/repo")),
            llm=LLMConfig(provider="ollama", ollama=None),  # Missing config
        )

        with pytest.raises(ValueError) as exc_info:
            await _create_llm_adapter(config)

        assert "Ollama configuration required" in str(exc_info.value)
