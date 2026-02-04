"""Tests for protocol interfaces."""

from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import pytest

from ai_issue_agent.interfaces.chat import ChatProvider
from ai_issue_agent.interfaces.llm import LLMProvider
from ai_issue_agent.interfaces.vcs import VCSProvider
from ai_issue_agent.models.analysis import CodeContext, ErrorAnalysis, SuggestedFix
from ai_issue_agent.models.issue import Issue, IssueCreate, IssueSearchResult, IssueState
from ai_issue_agent.models.message import ChatMessage
from ai_issue_agent.models.traceback import ParsedTraceback, StackFrame


class MockChatProvider:
    """Mock implementation of ChatProvider for testing protocol compliance."""

    async def connect(self) -> None:
        """Connect to chat platform."""
        pass

    async def disconnect(self) -> None:
        """Disconnect from chat platform."""
        pass

    async def listen(self) -> AsyncIterator[ChatMessage]:
        """Listen for messages."""
        # Yield a test message
        yield ChatMessage(
            channel_id="C123",
            message_id="M456",
            thread_id=None,
            user_id="U789",
            user_name="test",
            text="test message",
            timestamp=datetime.now(),
            raw_event={},
        )

    async def send_reply(
        self,
        channel_id: str,
        text: str,
        thread_id: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
    ) -> str:
        """Send a reply."""
        return "M999"

    async def add_reaction(
        self,
        channel_id: str,
        message_id: str,
        reaction: str,
    ) -> None:
        """Add a reaction."""
        pass

    async def remove_reaction(
        self,
        channel_id: str,
        message_id: str,
        reaction: str,
    ) -> None:
        """Remove a reaction."""
        pass


class MockVCSProvider:
    """Mock implementation of VCSProvider for testing protocol compliance."""

    async def search_issues(
        self,
        repo: str,
        query: str,
        state: str = "all",
        max_results: int = 10,
    ) -> list[IssueSearchResult]:
        """Search for issues."""
        issue = Issue(
            number=1,
            title="Test Issue",
            body="Body",
            url="https://example.com/1",
            state=IssueState.OPEN,
            labels=(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="user",
        )
        return [
            IssueSearchResult(
                issue=issue,
                relevance_score=0.9,
                matched_terms=("test",),
            )
        ]

    async def get_issue(
        self,
        repo: str,
        issue_number: int,
    ) -> Issue | None:
        """Get a specific issue."""
        return Issue(
            number=issue_number,
            title="Test Issue",
            body="Body",
            url=f"https://example.com/{issue_number}",
            state=IssueState.OPEN,
            labels=(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="user",
        )

    async def create_issue(
        self,
        repo: str,
        issue: IssueCreate,
    ) -> Issue:
        """Create a new issue."""
        return Issue(
            number=42,
            title=issue.title,
            body=issue.body,
            url="https://example.com/42",
            state=IssueState.OPEN,
            labels=issue.labels,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="bot",
        )

    async def clone_repository(
        self,
        repo: str,
        destination: Path,
        branch: str | None = None,
        shallow: bool = True,
    ) -> Path:
        """Clone a repository."""
        return destination / repo.replace("/", "_")

    async def get_file_content(
        self,
        repo: str,
        file_path: str,
        ref: str | None = None,
    ) -> str | None:
        """Get file content."""
        return "def test():\n    pass\n"

    async def get_default_branch(self, repo: str) -> str:
        """Get default branch."""
        return "main"


class MockLLMProvider:
    """Mock implementation of LLMProvider for testing protocol compliance."""

    async def analyze_error(
        self,
        traceback: ParsedTraceback,
        code_context: list[CodeContext],
        additional_context: str | None = None,
    ) -> ErrorAnalysis:
        """Analyze an error."""
        return ErrorAnalysis(
            root_cause="Test error",
            explanation="This is a test error",
            suggested_fixes=(),
            related_documentation=(),
            severity="low",
            confidence=0.8,
        )

    async def generate_issue_body(
        self,
        traceback: ParsedTraceback,
        analysis: ErrorAnalysis,
        code_context: list[CodeContext],
    ) -> str:
        """Generate issue body."""
        return "# Test Issue\n\nThis is a test issue."

    async def generate_issue_title(
        self,
        traceback: ParsedTraceback,
        analysis: ErrorAnalysis,
    ) -> str:
        """Generate issue title."""
        return f"{traceback.exception_type}: {traceback.exception_message[:50]}"

    async def calculate_similarity(
        self,
        traceback: ParsedTraceback,
        existing_issues: list[Issue],
    ) -> list[tuple[Issue, float]]:
        """Calculate similarity."""
        return [(issue, 0.75) for issue in existing_issues]

    @property
    def model_name(self) -> str:
        """Return model name."""
        return "test-model"

    @property
    def max_context_tokens(self) -> int:
        """Return max context tokens."""
        return 8000


class TestChatProviderProtocol:
    """Test ChatProvider protocol compliance."""

    def test_mock_chat_provider_implements_protocol(self):
        """Test that MockChatProvider implements ChatProvider protocol."""
        provider = MockChatProvider()
        # Check that the instance implements the protocol
        assert hasattr(provider, "connect")
        assert hasattr(provider, "disconnect")
        assert hasattr(provider, "listen")
        assert hasattr(provider, "send_reply")
        assert hasattr(provider, "add_reaction")
        assert hasattr(provider, "remove_reaction")

    @pytest.mark.asyncio
    async def test_chat_provider_connect(self):
        """Test connect method."""
        provider = MockChatProvider()
        await provider.connect()

    @pytest.mark.asyncio
    async def test_chat_provider_disconnect(self):
        """Test disconnect method."""
        provider = MockChatProvider()
        await provider.disconnect()

    @pytest.mark.asyncio
    async def test_chat_provider_listen(self):
        """Test listen method."""
        provider = MockChatProvider()
        messages = []
        async for message in provider.listen():
            messages.append(message)
            break  # Only get one message

        assert len(messages) == 1
        assert isinstance(messages[0], ChatMessage)

    @pytest.mark.asyncio
    async def test_chat_provider_send_reply(self):
        """Test send_reply method."""
        provider = MockChatProvider()
        message_id = await provider.send_reply(
            channel_id="C123",
            text="Hello",
        )
        assert isinstance(message_id, str)

    @pytest.mark.asyncio
    async def test_chat_provider_add_reaction(self):
        """Test add_reaction method."""
        provider = MockChatProvider()
        await provider.add_reaction(
            channel_id="C123",
            message_id="M456",
            reaction="eyes",
        )

    @pytest.mark.asyncio
    async def test_chat_provider_remove_reaction(self):
        """Test remove_reaction method."""
        provider = MockChatProvider()
        await provider.remove_reaction(
            channel_id="C123",
            message_id="M456",
            reaction="eyes",
        )


class TestVCSProviderProtocol:
    """Test VCSProvider protocol compliance."""

    def test_mock_vcs_provider_implements_protocol(self):
        """Test that MockVCSProvider implements VCSProvider protocol."""
        provider = MockVCSProvider()
        assert hasattr(provider, "search_issues")
        assert hasattr(provider, "get_issue")
        assert hasattr(provider, "create_issue")
        assert hasattr(provider, "clone_repository")
        assert hasattr(provider, "get_file_content")
        assert hasattr(provider, "get_default_branch")

    @pytest.mark.asyncio
    async def test_vcs_provider_search_issues(self):
        """Test search_issues method."""
        provider = MockVCSProvider()
        results = await provider.search_issues(
            repo="owner/repo",
            query="ValueError",
        )
        assert len(results) > 0
        assert isinstance(results[0], IssueSearchResult)

    @pytest.mark.asyncio
    async def test_vcs_provider_get_issue(self):
        """Test get_issue method."""
        provider = MockVCSProvider()
        issue = await provider.get_issue(repo="owner/repo", issue_number=42)
        assert issue is not None
        assert isinstance(issue, Issue)
        assert issue.number == 42

    @pytest.mark.asyncio
    async def test_vcs_provider_create_issue(self):
        """Test create_issue method."""
        provider = MockVCSProvider()
        issue_create = IssueCreate(title="New Issue", body="Body")
        issue = await provider.create_issue(repo="owner/repo", issue=issue_create)
        assert isinstance(issue, Issue)
        assert issue.title == "New Issue"

    @pytest.mark.asyncio
    async def test_vcs_provider_clone_repository(self):
        """Test clone_repository method."""
        provider = MockVCSProvider()
        dest = Path("/tmp/repos")
        result = await provider.clone_repository(
            repo="owner/repo",
            destination=dest,
        )
        assert isinstance(result, Path)

    @pytest.mark.asyncio
    async def test_vcs_provider_get_file_content(self):
        """Test get_file_content method."""
        provider = MockVCSProvider()
        content = await provider.get_file_content(
            repo="owner/repo",
            file_path="src/main.py",
        )
        assert content is not None
        assert isinstance(content, str)

    @pytest.mark.asyncio
    async def test_vcs_provider_get_default_branch(self):
        """Test get_default_branch method."""
        provider = MockVCSProvider()
        branch = await provider.get_default_branch(repo="owner/repo")
        assert isinstance(branch, str)
        assert branch == "main"


class TestLLMProviderProtocol:
    """Test LLMProvider protocol compliance."""

    def test_mock_llm_provider_implements_protocol(self):
        """Test that MockLLMProvider implements LLMProvider protocol."""
        provider = MockLLMProvider()
        assert hasattr(provider, "analyze_error")
        assert hasattr(provider, "generate_issue_body")
        assert hasattr(provider, "generate_issue_title")
        assert hasattr(provider, "calculate_similarity")
        assert hasattr(provider, "model_name")
        assert hasattr(provider, "max_context_tokens")

    @pytest.mark.asyncio
    async def test_llm_provider_analyze_error(self):
        """Test analyze_error method."""
        provider = MockLLMProvider()
        traceback = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test",
            frames=(StackFrame("/app/main.py", 1, "foo"),),
            raw_text="...",
        )
        analysis = await provider.analyze_error(
            traceback=traceback,
            code_context=[],
        )
        assert isinstance(analysis, ErrorAnalysis)

    @pytest.mark.asyncio
    async def test_llm_provider_generate_issue_body(self):
        """Test generate_issue_body method."""
        provider = MockLLMProvider()
        traceback = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test",
            frames=(StackFrame("/app/main.py", 1, "foo"),),
            raw_text="...",
        )
        analysis = ErrorAnalysis(
            root_cause="test",
            explanation="test",
            suggested_fixes=(),
            related_documentation=(),
            severity="low",
            confidence=0.5,
        )
        body = await provider.generate_issue_body(
            traceback=traceback,
            analysis=analysis,
            code_context=[],
        )
        assert isinstance(body, str)

    @pytest.mark.asyncio
    async def test_llm_provider_generate_issue_title(self):
        """Test generate_issue_title method."""
        provider = MockLLMProvider()
        traceback = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test error message",
            frames=(StackFrame("/app/main.py", 1, "foo"),),
            raw_text="...",
        )
        analysis = ErrorAnalysis(
            root_cause="test",
            explanation="test",
            suggested_fixes=(),
            related_documentation=(),
            severity="low",
            confidence=0.5,
        )
        title = await provider.generate_issue_title(
            traceback=traceback,
            analysis=analysis,
        )
        assert isinstance(title, str)
        assert "ValueError" in title

    @pytest.mark.asyncio
    async def test_llm_provider_calculate_similarity(self):
        """Test calculate_similarity method."""
        provider = MockLLMProvider()
        traceback = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test",
            frames=(StackFrame("/app/main.py", 1, "foo"),),
            raw_text="...",
        )
        issue = Issue(
            number=1,
            title="Test",
            body="Body",
            url="https://example.com/1",
            state=IssueState.OPEN,
            labels=(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="user",
        )
        results = await provider.calculate_similarity(
            traceback=traceback,
            existing_issues=[issue],
        )
        assert len(results) == 1
        assert isinstance(results[0], tuple)
        assert isinstance(results[0][0], Issue)
        assert isinstance(results[0][1], float)

    def test_llm_provider_model_name_property(self):
        """Test model_name property."""
        provider = MockLLMProvider()
        assert isinstance(provider.model_name, str)
        assert provider.model_name == "test-model"

    def test_llm_provider_max_context_tokens_property(self):
        """Test max_context_tokens property."""
        provider = MockLLMProvider()
        assert isinstance(provider.max_context_tokens, int)
        assert provider.max_context_tokens > 0
