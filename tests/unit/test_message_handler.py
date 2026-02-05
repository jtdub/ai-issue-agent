"""Tests for MessageHandler functionality."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

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
from ai_issue_agent.core.message_handler import MessageHandler
from ai_issue_agent.models.analysis import CodeContext, ErrorAnalysis, SuggestedFix
from ai_issue_agent.models.issue import Issue, IssueMatch, IssueState
from ai_issue_agent.models.message import ChatMessage, ProcessingResult
from ai_issue_agent.models.traceback import ParsedTraceback, StackFrame


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
                processing_reaction="eyes",
                complete_reaction="white_check_mark",
                error_reaction="x",
            ),
        ),
        vcs=VCSConfig(
            provider="github",
            github=GitHubConfig(
                default_repo="owner/repo",
                default_labels=["auto-triaged"],
            ),
            channel_repos={"C123456": "owner/channel-repo"},
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
    return AsyncMock()


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
    return MagicMock()


@pytest.fixture
def mock_matcher() -> AsyncMock:
    """Create a mock issue matcher."""
    return AsyncMock()


@pytest.fixture
def mock_analyzer() -> AsyncMock:
    """Create a mock code analyzer."""
    return AsyncMock()


@pytest.fixture
def message_handler(
    mock_chat: AsyncMock,
    mock_vcs: AsyncMock,
    mock_llm: AsyncMock,
    mock_parser: MagicMock,
    mock_matcher: AsyncMock,
    mock_analyzer: AsyncMock,
    agent_config: AgentConfig,
) -> MessageHandler:
    """Create a MessageHandler instance for testing."""
    return MessageHandler(
        chat=mock_chat,
        vcs=mock_vcs,
        llm=mock_llm,
        parser=mock_parser,
        matcher=mock_matcher,
        analyzer=mock_analyzer,
        config=agent_config,
    )


@pytest.fixture
def sample_message() -> ChatMessage:
    """Create a sample chat message."""
    return ChatMessage(
        channel_id="C123456",
        message_id="M123456",
        thread_id=None,
        user_id="U123456",
        user_name="testuser",
        text=(
            "Error occurred:\nTraceback (most recent call last):\n"
            '  File "test.py", line 1\nValueError: test error'
        ),
        timestamp=datetime.now(),
        raw_event={},
    )


@pytest.fixture
def sample_traceback() -> ParsedTraceback:
    """Create a sample parsed traceback."""
    return ParsedTraceback(
        exception_type="ValueError",
        exception_message="test error",
        frames=(
            StackFrame(
                file_path="src/app/test.py",
                line_number=42,
                function_name="test_func",
            ),
        ),
        raw_text="Traceback...",
    )


@pytest.fixture
def sample_issue() -> Issue:
    """Create a sample issue."""
    return Issue(
        number=123,
        title="ValueError: test error",
        body="Test issue body",
        url="https://github.com/owner/repo/issues/123",
        state=IssueState.OPEN,
        labels=("auto-triaged",),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        author="bot",
    )


@pytest.fixture
def sample_analysis() -> ErrorAnalysis:
    """Create a sample error analysis."""
    return ErrorAnalysis(
        root_cause="Invalid input",
        explanation="The input value was not valid",
        suggested_fixes=(
            SuggestedFix(
                description="Add input validation",
                file_path="test.py",
                original_code="x = int(value)",
                fixed_code="x = int(value) if value.isdigit() else 0",
                confidence=0.9,
            ),
        ),
        related_documentation=("https://docs.python.org/3/library/functions.html#int",),
        severity="medium",
        confidence=0.85,
    )


class TestMessageHandler:
    """Tests for MessageHandler class."""

    def test_init(
        self,
        message_handler: MessageHandler,
        agent_config: AgentConfig,
    ) -> None:
        """Test MessageHandler initialization."""
        assert message_handler._config == agent_config
        assert message_handler._processing_reaction == "eyes"
        assert message_handler._complete_reaction == "white_check_mark"
        assert message_handler._error_reaction == "x"

    @pytest.mark.asyncio
    async def test_handle_no_traceback(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
        mock_parser: MagicMock,
        sample_message: ChatMessage,
    ) -> None:
        """Test handling message with no traceback."""
        mock_parser.contains_traceback.return_value = False

        result = await message_handler.handle(sample_message)

        assert result == ProcessingResult.NO_TRACEBACK
        mock_chat.add_reaction.assert_called_once()
        mock_chat.remove_reaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_existing_issue_linked(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
        mock_parser: MagicMock,
        mock_matcher: AsyncMock,
        sample_message: ChatMessage,
        sample_traceback: ParsedTraceback,
        sample_issue: Issue,
    ) -> None:
        """Test handling message with existing issue match."""
        mock_parser.contains_traceback.return_value = True
        mock_parser.parse.return_value = sample_traceback
        mock_matcher.find_matches.return_value = [
            IssueMatch(
                issue=sample_issue,
                confidence=0.95,
                match_reasons=("exact_match",),
            ),
        ]

        result = await message_handler.handle(sample_message)

        assert result == ProcessingResult.EXISTING_ISSUE_LINKED
        # Should send reply with issue link
        mock_chat.send_reply.assert_called_once()
        call_args = mock_chat.send_reply.call_args
        assert sample_issue.url in call_args.kwargs.get(
            "text", call_args.args[1] if len(call_args.args) > 1 else ""
        )

    @pytest.mark.asyncio
    async def test_handle_new_issue_created(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
        mock_parser: MagicMock,
        mock_matcher: AsyncMock,
        mock_analyzer: AsyncMock,
        mock_llm: AsyncMock,
        mock_vcs: AsyncMock,
        sample_message: ChatMessage,
        sample_traceback: ParsedTraceback,
        sample_issue: Issue,
        sample_analysis: ErrorAnalysis,
    ) -> None:
        """Test handling message that creates new issue."""
        mock_parser.contains_traceback.return_value = True
        mock_parser.parse.return_value = sample_traceback
        mock_matcher.find_matches.return_value = []  # No matches
        mock_analyzer.analyze.return_value = [
            CodeContext(
                file_path="test.py",
                start_line=40,
                end_line=45,
                content="def test_func():\n    x = int(value)",
                highlight_line=42,
            ),
        ]
        mock_llm.analyze_error.return_value = sample_analysis
        mock_llm.generate_issue_title.return_value = "ValueError: test error"
        mock_llm.generate_issue_body.return_value = "## Error\nTest error occurred"
        mock_vcs.create_issue.return_value = sample_issue

        result = await message_handler.handle(sample_message)

        assert result == ProcessingResult.NEW_ISSUE_CREATED
        mock_vcs.create_issue.assert_called_once()
        # Should send reply with new issue link
        assert mock_chat.send_reply.call_count >= 1

    @pytest.mark.asyncio
    async def test_handle_error(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
        mock_parser: MagicMock,
        sample_message: ChatMessage,
    ) -> None:
        """Test handling message that causes error."""
        mock_parser.contains_traceback.return_value = True
        mock_parser.parse.side_effect = Exception("Parse error")

        result = await message_handler.handle(sample_message)

        # Since contains_traceback returns True but parse fails,
        # it should return NO_TRACEBACK as per the implementation
        assert result in (ProcessingResult.NO_TRACEBACK, ProcessingResult.ERROR)

    @pytest.mark.asyncio
    async def test_handle_no_repository_mapped(
        self,
        mock_chat: AsyncMock,
        mock_vcs: AsyncMock,
        mock_llm: AsyncMock,
        mock_parser: MagicMock,
        mock_matcher: AsyncMock,
        mock_analyzer: AsyncMock,
        sample_traceback: ParsedTraceback,
    ) -> None:
        """Test handling message from unmapped channel."""
        # Create config with no channel mapping and no default repo
        config = AgentConfig(
            chat=ChatConfig(
                provider="slack",
                slack=SlackConfig(
                    bot_token="xoxb-test",
                    app_token="xapp-test",
                ),
            ),
            vcs=VCSConfig(
                provider="github",
                github=None,  # No default repo
                channel_repos={},  # No mappings
            ),
            llm=LLMConfig(provider="openai", openai=OpenAIConfig(api_key="sk-test")),
        )

        handler = MessageHandler(
            mock_chat,
            mock_vcs,
            mock_llm,
            mock_parser,
            mock_matcher,
            mock_analyzer,
            config,
        )

        mock_parser.contains_traceback.return_value = True
        mock_parser.parse.return_value = sample_traceback

        message = ChatMessage(
            channel_id="UNMAPPED",
            message_id="M123",
            thread_id=None,
            user_id="U123",
            user_name="test",
            text="error",
            timestamp=datetime.now(),
            raw_event={},
        )

        result = await handler.handle(message)

        assert result == ProcessingResult.ERROR
        # Should send error reply
        mock_chat.send_reply.assert_called()

    def test_get_repository_for_channel_mapped(
        self,
        message_handler: MessageHandler,
    ) -> None:
        """Test getting repository for mapped channel."""
        repo = message_handler._get_repository_for_channel("C123456")
        assert repo == "owner/channel-repo"

    def test_get_repository_for_channel_default(
        self,
        message_handler: MessageHandler,
    ) -> None:
        """Test getting repository falls back to default."""
        repo = message_handler._get_repository_for_channel("UNKNOWN")
        assert repo == "owner/repo"  # Default from config

    def test_get_default_labels(
        self,
        message_handler: MessageHandler,
    ) -> None:
        """Test getting default labels."""
        labels = message_handler._get_default_labels()
        assert "auto-triaged" in labels

    @pytest.mark.asyncio
    async def test_add_reaction_error_handling(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
    ) -> None:
        """Test that reaction errors are handled gracefully."""
        mock_chat.add_reaction.side_effect = Exception("Reaction failed")

        # Should not raise
        await message_handler._add_reaction("C123", "M123", "eyes")

    @pytest.mark.asyncio
    async def test_remove_reaction_error_handling(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
    ) -> None:
        """Test that reaction removal errors are handled gracefully."""
        mock_chat.remove_reaction.side_effect = Exception("Removal failed")

        # Should not raise
        await message_handler._remove_reaction("C123", "M123", "eyes")

    @pytest.mark.asyncio
    async def test_update_reaction(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
    ) -> None:
        """Test updating reaction (remove old, add new)."""
        await message_handler._update_reaction("C123", "M123", "eyes", "white_check_mark")

        mock_chat.remove_reaction.assert_called_with("C123", "M123", "eyes")
        mock_chat.add_reaction.assert_called_with("C123", "M123", "white_check_mark")

    @pytest.mark.asyncio
    async def test_send_existing_issue_reply(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
        sample_issue: Issue,
    ) -> None:
        """Test sending reply for existing issue."""
        await message_handler._send_existing_issue_reply("C123", "T123", sample_issue, 0.95)

        mock_chat.send_reply.assert_called_once()
        call_kwargs = mock_chat.send_reply.call_args.kwargs
        assert call_kwargs["channel_id"] == "C123"
        assert call_kwargs["thread_id"] == "T123"
        assert "95%" in call_kwargs["text"]  # Confidence percentage

    @pytest.mark.asyncio
    async def test_send_new_issue_reply(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
        sample_issue: Issue,
    ) -> None:
        """Test sending reply for new issue."""
        await message_handler._send_new_issue_reply("C123", "T123", sample_issue)

        mock_chat.send_reply.assert_called_once()
        call_kwargs = mock_chat.send_reply.call_args.kwargs
        assert sample_issue.url in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_send_error_reply(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
    ) -> None:
        """Test sending error reply."""
        await message_handler._send_error_reply("C123", "T123", "Something went wrong")

        mock_chat.send_reply.assert_called_once()
        call_kwargs = mock_chat.send_reply.call_args.kwargs
        assert "⚠️" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_handle_replies_in_thread(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
        mock_parser: MagicMock,
        mock_matcher: AsyncMock,
        sample_traceback: ParsedTraceback,
        sample_issue: Issue,
    ) -> None:
        """Test that replies are sent to the thread."""
        mock_parser.contains_traceback.return_value = True
        mock_parser.parse.return_value = sample_traceback
        mock_matcher.find_matches.return_value = [
            IssueMatch(issue=sample_issue, confidence=0.95, match_reasons=()),
        ]

        # Message already in a thread
        message = ChatMessage(
            channel_id="C123",
            message_id="M123",
            thread_id="T999",  # Existing thread
            user_id="U123",
            user_name="test",
            text="error",
            timestamp=datetime.now(),
            raw_event={},
        )

        await message_handler.handle(message)

        # Reply should be in the existing thread
        call_kwargs = mock_chat.send_reply.call_args.kwargs
        assert call_kwargs["thread_id"] == "T999"

    @pytest.mark.asyncio
    async def test_handle_uses_message_id_as_thread_if_no_thread(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
        mock_parser: MagicMock,
        mock_matcher: AsyncMock,
        sample_traceback: ParsedTraceback,
        sample_issue: Issue,
    ) -> None:
        """Test that message_id is used as thread_id when not in thread."""
        mock_parser.contains_traceback.return_value = True
        mock_parser.parse.return_value = sample_traceback
        mock_matcher.find_matches.return_value = [
            IssueMatch(issue=sample_issue, confidence=0.95, match_reasons=()),
        ]

        # Message not in a thread
        message = ChatMessage(
            channel_id="C123",
            message_id="M123",
            thread_id=None,  # Not in thread
            user_id="U123",
            user_name="test",
            text="error",
            timestamp=datetime.now(),
            raw_event={},
        )

        await message_handler.handle(message)

        # Reply should create new thread with message_id
        call_kwargs = mock_chat.send_reply.call_args.kwargs
        assert call_kwargs["thread_id"] == "M123"

    @pytest.mark.asyncio
    async def test_handle_low_confidence_creates_new_issue(
        self,
        message_handler: MessageHandler,
        mock_chat: AsyncMock,
        mock_parser: MagicMock,
        mock_matcher: AsyncMock,
        mock_analyzer: AsyncMock,
        mock_llm: AsyncMock,
        mock_vcs: AsyncMock,
        sample_message: ChatMessage,
        sample_traceback: ParsedTraceback,
        sample_issue: Issue,
        sample_analysis: ErrorAnalysis,
    ) -> None:
        """Test that low confidence matches result in new issue creation."""
        mock_parser.contains_traceback.return_value = True
        mock_parser.parse.return_value = sample_traceback
        # Return match with low confidence (below threshold)
        mock_matcher.find_matches.return_value = [
            IssueMatch(
                issue=sample_issue,
                confidence=0.5,  # Below 0.85 threshold
                match_reasons=("partial_match",),
            ),
        ]
        mock_analyzer.analyze.return_value = []
        mock_llm.analyze_error.return_value = sample_analysis
        mock_llm.generate_issue_title.return_value = "New Issue"
        mock_llm.generate_issue_body.return_value = "Body"
        mock_vcs.create_issue.return_value = sample_issue

        result = await message_handler.handle(sample_message)

        assert result == ProcessingResult.NEW_ISSUE_CREATED
        mock_vcs.create_issue.assert_called_once()
