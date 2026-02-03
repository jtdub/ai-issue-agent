# AI Issue Agent - Architecture Blueprint
 
## Table of Contents
1. [Overview](#overview)
2. [Directory Structure](#directory-structure)
3. [Abstract Interfaces](#abstract-interfaces)
4. [Core Classes](#core-classes)
5. [Data Models](#data-models)
6. [Workflow State Machine](#workflow-state-machine)
7. [Dependencies](#dependencies)
8. [Configuration Schema](#configuration-schema)
9. [Edge Cases and Error Handling](#edge-cases-and-error-handling)
10. [Testing Strategy](#testing-strategy)
 
---
 
## Overview
 
The AI Issue Agent monitors chat platforms (starting with Slack) for Python tracebacks. When detected, it:
1. Parses the traceback to extract structured error information
2. Searches existing GitHub issues for matches
3. Either links to an existing issue or creates a new one with LLM-powered analysis
 
### Design Principles
- **Pluggable adapters**: Chat, VCS, and LLM providers are swappable via configuration
- **Async-first**: All I/O operations use async/await for concurrency
- **Clean separation**: Interfaces define contracts; adapters implement them; core logic is provider-agnostic
- **CLI-based VCS operations**: Uses `gh` CLI for GitHub (simplifies auth, avoids API complexity)
 
---
 
## Directory Structure
 
```
ai-issue-agent/
├── src/
│   └── ai_issue_agent/
│       ├── __init__.py
│       ├── __main__.py              # Entry point: python -m ai_issue_agent
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   ├── schema.py            # Pydantic models for configuration
│       │   └── loader.py            # YAML + env var loading
│       │
│       ├── interfaces/              # Abstract base classes (protocols)
│       │   ├── __init__.py
│       │   ├── chat.py              # ChatProvider protocol
│       │   ├── vcs.py               # VCSProvider protocol
│       │   └── llm.py               # LLMProvider protocol
│       │
│       ├── adapters/                # Concrete implementations
│       │   ├── __init__.py
│       │   ├── chat/
│       │   │   ├── __init__.py
│       │   │   ├── slack.py         # Slack via slack-bolt
│       │   │   ├── discord.py       # Future: Discord
│       │   │   └── teams.py         # Future: MS Teams
│       │   ├── vcs/
│       │   │   ├── __init__.py
│       │   │   ├── github.py        # GitHub via gh CLI
│       │   │   ├── gitlab.py        # Future: GitLab
│       │   │   └── bitbucket.py     # Future: Bitbucket
│       │   └── llm/
│       │       ├── __init__.py
│       │       ├── base.py          # Shared utilities for LLM adapters
│       │       ├── openai.py        # OpenAI API
│       │       ├── anthropic.py     # Anthropic API
│       │       └── ollama.py        # Local Ollama/Llama
│       │
│       ├── core/                    # Provider-agnostic business logic
│       │   ├── __init__.py
│       │   ├── agent.py             # Main orchestrator
│       │   ├── traceback_parser.py  # Python traceback parsing
│       │   ├── issue_matcher.py     # Issue search & similarity matching
│       │   ├── code_analyzer.py     # Repository code analysis
│       │   └── message_handler.py   # Message processing pipeline
│       │
│       ├── models/                  # Data transfer objects
│       │   ├── __init__.py
│       │   ├── traceback.py         # ParsedTraceback, StackFrame
│       │   ├── issue.py             # Issue, IssueSearchResult
│       │   ├── message.py           # ChatMessage, ChatReply
│       │   └── analysis.py          # ErrorAnalysis, SuggestedFix
│       │
│       └── utils/
│           ├── __init__.py
│           ├── async_helpers.py     # Retry logic, rate limiting
│           └── text.py              # Text processing utilities
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Shared fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_traceback_parser.py
│   │   ├── test_issue_matcher.py
│   │   └── test_config_loader.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_slack_adapter.py
│   │   ├── test_github_adapter.py
│   │   └── test_llm_adapters.py
│   ├── e2e/
│   │   ├── __init__.py
│   │   └── test_full_workflow.py
│   └── fixtures/
│       ├── tracebacks/              # Sample Python tracebacks
│       │   ├── simple.txt
│       │   ├── nested.txt
│       │   └── multiline.txt
│       └── issues/                  # Sample GitHub issues
│           └── sample_issues.json
│
├── config/
│   ├── config.example.yaml          # Template configuration
│   └── config.schema.json           # JSON Schema for validation
│
├── scripts/
│   └── setup_dev.sh                 # Development environment setup
│
├── docs/
│   ├── ARCHITECTURE.md              # This document
│   ├── DEVELOPMENT.md               # Developer guide
│   └── DEPLOYMENT.md                # Deployment instructions
│
├── pyproject.toml                   # Project metadata and dependencies
├── README.md
├── LICENSE
└── .gitignore
```
 
---
 
## Abstract Interfaces
 
### ChatProvider Protocol
 
```python
# src/ai_issue_agent/interfaces/chat.py
 
from typing import Protocol, AsyncIterator, Optional
from ..models.message import ChatMessage, ChatReply
 
class ChatProvider(Protocol):
    """Abstract interface for chat platform integrations."""
 
    async def connect(self) -> None:
        """
        Establish connection to the chat platform.
 
        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If credentials are invalid
        """
        ...
 
    async def disconnect(self) -> None:
        """Gracefully close the connection."""
        ...
 
    async def listen(self) -> AsyncIterator[ChatMessage]:
        """
        Yield incoming messages from monitored channels.
 
        This is an async generator that yields messages as they arrive.
        It should handle reconnection internally on transient failures.
 
        Yields:
            ChatMessage: Each incoming message
        """
        ...
 
    async def send_reply(
        self,
        channel_id: str,
        text: str,
        thread_id: Optional[str] = None,
        blocks: Optional[list] = None,  # Platform-specific rich formatting
    ) -> str:
        """
        Send a reply to a channel, optionally in a thread.
 
        Args:
            channel_id: Target channel identifier
            text: Plain text message (fallback)
            thread_id: Parent message ID for threading
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
 
        Used to acknowledge receipt (e.g., :eyes: when processing).
 
        Args:
            channel_id: Channel containing the message
            message_id: Target message identifier
            reaction: Reaction name (without colons)
        """
        ...
 
    async def remove_reaction(
        self,
        channel_id: str,
        message_id: str,
        reaction: str,
    ) -> None:
        """Remove a previously added reaction."""
        ...
```
 
### VCSProvider Protocol
 
```python
# src/ai_issue_agent/interfaces/vcs.py
 
from typing import Protocol, Optional
from pathlib import Path
from ..models.issue import Issue, IssueSearchResult, IssueCreate
 
class VCSProvider(Protocol):
    """Abstract interface for version control system integrations."""
 
    async def search_issues(
        self,
        repo: str,
        query: str,
        state: str = "all",  # "open", "closed", "all"
        max_results: int = 10,
    ) -> list[IssueSearchResult]:
        """
        Search for issues matching the query.
 
        Args:
            repo: Repository identifier (e.g., "owner/repo")
            query: Search query string
            state: Filter by issue state
            max_results: Maximum number of results to return
 
        Returns:
            List of matching issues with relevance scores
        """
        ...
 
    async def get_issue(
        self,
        repo: str,
        issue_number: int,
    ) -> Optional[Issue]:
        """
        Fetch a specific issue by number.
 
        Args:
            repo: Repository identifier
            issue_number: Issue number
 
        Returns:
            Issue if found, None otherwise
        """
        ...
 
    async def create_issue(
        self,
        repo: str,
        issue: IssueCreate,
    ) -> Issue:
        """
        Create a new issue in the repository.
 
        Args:
            repo: Repository identifier
            issue: Issue creation data
 
        Returns:
            The created issue with assigned number and URL
 
        Raises:
            CreateError: If issue creation fails
        """
        ...
 
    async def clone_repository(
        self,
        repo: str,
        destination: Path,
        branch: Optional[str] = None,
        shallow: bool = True,
    ) -> Path:
        """
        Clone a repository to a local directory.
 
        Args:
            repo: Repository identifier
            destination: Local directory path
            branch: Specific branch to clone (default: default branch)
            shallow: If True, perform shallow clone (--depth 1)
 
        Returns:
            Path to the cloned repository
 
        Raises:
            CloneError: If cloning fails
        """
        ...
 
    async def get_file_content(
        self,
        repo: str,
        file_path: str,
        ref: Optional[str] = None,  # branch, tag, or commit
    ) -> Optional[str]:
        """
        Fetch content of a file from the repository.
 
        Useful for reading files without full clone.
 
        Args:
            repo: Repository identifier
            file_path: Path to file within repository
            ref: Git reference (default: default branch HEAD)
 
        Returns:
            File contents as string, None if file doesn't exist
        """
        ...
 
    async def get_default_branch(self, repo: str) -> str:
        """Get the default branch name for a repository."""
        ...
```
 
### LLMProvider Protocol
 
```python
# src/ai_issue_agent/interfaces/llm.py
 
from typing import Protocol, Optional
from ..models.traceback import ParsedTraceback
from ..models.analysis import ErrorAnalysis, CodeContext
 
class LLMProvider(Protocol):
    """Abstract interface for LLM integrations."""
 
    async def analyze_error(
        self,
        traceback: ParsedTraceback,
        code_context: list[CodeContext],
        additional_context: Optional[str] = None,
    ) -> ErrorAnalysis:
        """
        Analyze an error traceback with surrounding code context.
 
        Args:
            traceback: Parsed traceback information
            code_context: Relevant code snippets from referenced files
            additional_context: Optional additional information (e.g., README)
 
        Returns:
            Analysis including root cause and suggested fixes
        """
        ...
 
    async def generate_issue_body(
        self,
        traceback: ParsedTraceback,
        analysis: ErrorAnalysis,
        code_context: list[CodeContext],
    ) -> str:
        """
        Generate a well-formatted issue body.
 
        Args:
            traceback: Original traceback data
            analysis: LLM analysis results
            code_context: Code snippets for reference
 
        Returns:
            Markdown-formatted issue body
        """
        ...
 
    async def generate_issue_title(
        self,
        traceback: ParsedTraceback,
        analysis: ErrorAnalysis,
    ) -> str:
        """
        Generate a concise, descriptive issue title.
 
        Args:
            traceback: Parsed traceback
            analysis: Error analysis
 
        Returns:
            Issue title (max ~80 characters)
        """
        ...
 
    async def calculate_similarity(
        self,
        traceback: ParsedTraceback,
        existing_issues: list[Issue],
    ) -> list[tuple[Issue, float]]:
        """
        Calculate similarity between a traceback and existing issues.
 
        Used to determine if an issue already exists for this error.
 
        Args:
            traceback: Parsed traceback to match
            existing_issues: Candidate issues to compare against
 
        Returns:
            List of (issue, similarity_score) tuples, sorted by score desc
        """
        ...
 
    @property
    def model_name(self) -> str:
        """Return the model identifier being used."""
        ...
 
    @property
    def max_context_tokens(self) -> int:
        """Return the maximum context window size."""
        ...
```
 
---
 
## Core Classes
 
### Agent (Main Orchestrator)
 
```python
# src/ai_issue_agent/core/agent.py
 
class Agent:
    """
    Main orchestrator that coordinates all components.
 
    Responsibilities:
    - Initialize and manage adapter instances
    - Route incoming messages through the processing pipeline
    - Handle graceful startup and shutdown
    - Manage concurrent message processing
 
    Attributes:
        config: Application configuration
        chat: Chat provider adapter
        vcs: VCS provider adapter
        llm: LLM provider adapter
        message_handler: Message processing pipeline
    """
 
    def __init__(
        self,
        config: AgentConfig,
        chat: ChatProvider,
        vcs: VCSProvider,
        llm: LLMProvider,
    ) -> None: ...
 
    async def start(self) -> None:
        """Start the agent and begin processing messages."""
 
    async def stop(self) -> None:
        """Gracefully stop the agent."""
 
    async def process_message(self, message: ChatMessage) -> None:
        """Process a single message through the pipeline."""
```
 
### TracebackParser
 
```python
# src/ai_issue_agent/core/traceback_parser.py
 
class TracebackParser:
    """
    Parser for Python tracebacks.
 
    Responsibilities:
    - Detect if text contains a Python traceback
    - Extract exception type, message, and stack frames
    - Handle various traceback formats (standard, chained, syntax errors)
    - Normalize file paths for matching
 
    Supports:
    - Standard tracebacks
    - Chained exceptions (raise ... from ...)
    - SyntaxError tracebacks
    - Tracebacks in code blocks (```)
    - Multi-line exception messages
    """
 
    def contains_traceback(self, text: str) -> bool:
        """Check if text contains a Python traceback."""
 
    def parse(self, text: str) -> ParsedTraceback:
        """
        Parse a Python traceback from text.
 
        Raises:
            TracebackParseError: If no valid traceback found
        """
 
    def extract_all(self, text: str) -> list[ParsedTraceback]:
        """Extract all tracebacks from text (for chained exceptions)."""
```
 
### IssueMatcher
 
```python
# src/ai_issue_agent/core/issue_matcher.py
 
class IssueMatcher:
    """
    Finds existing issues that match a traceback.
 
    Responsibilities:
    - Build search queries from parsed tracebacks
    - Search VCS issues using multiple strategies
    - Score and rank potential matches
    - Determine if a match is "close enough"
 
    Matching Strategies:
    1. Exact exception match: Same exception type and message
    2. Similar stack trace: Overlapping file/function names
    3. Semantic similarity: LLM-based similarity scoring
    """
 
    def __init__(
        self,
        vcs: VCSProvider,
        llm: LLMProvider,
        config: MatcherConfig,
    ) -> None: ...
 
    async def find_matches(
        self,
        repo: str,
        traceback: ParsedTraceback,
    ) -> list[IssueMatch]:
        """
        Find existing issues matching the traceback.
 
        Returns:
            List of matches with confidence scores, sorted by confidence
        """
 
    def build_search_query(self, traceback: ParsedTraceback) -> str:
        """Build a search query string from traceback data."""
```
 
### CodeAnalyzer
 
```python
# src/ai_issue_agent/core/code_analyzer.py
 
class CodeAnalyzer:
    """
    Analyzes repository code related to a traceback.
 
    Responsibilities:
    - Clone repository (if needed)
    - Extract code context for stack frame locations
    - Gather additional context (imports, related files)
    - Prepare code for LLM analysis
    """
 
    def __init__(
        self,
        vcs: VCSProvider,
        config: AnalyzerConfig,
    ) -> None: ...
 
    async def analyze(
        self,
        repo: str,
        traceback: ParsedTraceback,
    ) -> list[CodeContext]:
        """
        Extract code context for all stack frames.
 
        Returns:
            List of code contexts for each relevant file
        """
 
    async def get_surrounding_code(
        self,
        repo_path: Path,
        file_path: str,
        line_number: int,
        context_lines: int = 10,
    ) -> CodeContext:
        """Get code surrounding a specific line."""
```
 
### MessageHandler
 
```python
# src/ai_issue_agent/core/message_handler.py
 
class MessageHandler:
    """
    Orchestrates the message processing pipeline.
 
    Responsibilities:
    - Coordinate traceback parsing, issue matching, and analysis
    - Decide whether to link existing or create new issue
    - Format and send replies
    - Track processing state for observability
    """
 
    def __init__(
        self,
        chat: ChatProvider,
        vcs: VCSProvider,
        llm: LLMProvider,
        parser: TracebackParser,
        matcher: IssueMatcher,
        analyzer: CodeAnalyzer,
        config: HandlerConfig,
    ) -> None: ...
 
    async def handle(self, message: ChatMessage) -> ProcessingResult:
        """
        Process a message through the full pipeline.
 
        Returns:
            ProcessingResult indicating what action was taken
        """
```
 
---
 
## Data Models
 
```python
# src/ai_issue_agent/models/traceback.py
 
from dataclasses import dataclass
from typing import Optional
 
@dataclass(frozen=True)
class StackFrame:
    """A single frame in a Python stack trace."""
    file_path: str
    line_number: int
    function_name: str
    code_line: Optional[str] = None  # The actual code at this line
 
    @property
    def is_stdlib(self) -> bool:
        """Check if this frame is from Python standard library."""
 
    @property
    def is_site_packages(self) -> bool:
        """Check if this frame is from third-party packages."""
 
    @property
    def normalized_path(self) -> str:
        """Path relative to project root, without absolute prefixes."""
 
@dataclass(frozen=True)
class ParsedTraceback:
    """A fully parsed Python traceback."""
    exception_type: str           # e.g., "ValueError"
    exception_message: str        # e.g., "invalid literal for int()"
    frames: tuple[StackFrame, ...]
    raw_text: str                 # Original traceback text
    is_chained: bool = False      # Part of exception chain
    cause: Optional['ParsedTraceback'] = None  # __cause__ exception
 
    @property
    def innermost_frame(self) -> StackFrame:
        """The frame where the exception was raised."""
 
    @property
    def project_frames(self) -> tuple[StackFrame, ...]:
        """Frames from project code (not stdlib/site-packages)."""
 
    @property
    def signature(self) -> str:
        """Unique signature for deduplication: 'ExceptionType: message'."""
```
 
```python
# src/ai_issue_agent/models/issue.py
 
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum
 
class IssueState(Enum):
    OPEN = "open"
    CLOSED = "closed"
 
@dataclass(frozen=True)
class Issue:
    """A VCS issue (GitHub, GitLab, etc.)."""
    number: int
    title: str
    body: str
    url: str
    state: IssueState
    labels: tuple[str, ...]
    created_at: datetime
    updated_at: datetime
    author: str
 
@dataclass(frozen=True)
class IssueSearchResult:
    """An issue returned from search with relevance info."""
    issue: Issue
    relevance_score: float  # 0.0 to 1.0, from search engine
    matched_terms: tuple[str, ...]
 
@dataclass(frozen=True)
class IssueCreate:
    """Data for creating a new issue."""
    title: str
    body: str
    labels: tuple[str, ...] = ()
    assignees: tuple[str, ...] = ()
 
@dataclass(frozen=True)
class IssueMatch:
    """A potential match between a traceback and existing issue."""
    issue: Issue
    confidence: float  # 0.0 to 1.0
    match_reasons: tuple[str, ...]  # Why we think it matches
```
 
```python
# src/ai_issue_agent/models/message.py
 
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum
 
@dataclass(frozen=True)
class ChatMessage:
    """An incoming message from a chat platform."""
    channel_id: str
    message_id: str
    thread_id: Optional[str]  # None if not in a thread
    user_id: str
    user_name: str
    text: str
    timestamp: datetime
 
    # Platform-specific metadata
    raw_event: dict  # Original event payload
 
@dataclass(frozen=True)
class ChatReply:
    """A reply to send to chat."""
    channel_id: str
    text: str
    thread_id: Optional[str] = None
    blocks: Optional[list] = None  # Rich formatting
 
class ProcessingResult(Enum):
    """Outcome of processing a message."""
    NO_TRACEBACK = "no_traceback"
    EXISTING_ISSUE_LINKED = "existing_issue_linked"
    NEW_ISSUE_CREATED = "new_issue_created"
    ERROR = "error"
```
 
```python
# src/ai_issue_agent/models/analysis.py
 
from dataclasses import dataclass
from typing import Optional
 
@dataclass(frozen=True)
class CodeContext:
    """Code snippet with surrounding context."""
    file_path: str
    start_line: int
    end_line: int
    content: str
    highlight_line: Optional[int] = None  # Line to emphasize (error location)
 
    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1
 
@dataclass(frozen=True)
class SuggestedFix:
    """A suggested code fix."""
    description: str
    file_path: str
    original_code: str
    fixed_code: str
    confidence: float  # 0.0 to 1.0
 
@dataclass(frozen=True)
class ErrorAnalysis:
    """LLM analysis of an error."""
    root_cause: str
    explanation: str
    suggested_fixes: tuple[SuggestedFix, ...]
    related_documentation: tuple[str, ...]  # Links to relevant docs
    severity: str  # "low", "medium", "high", "critical"
    confidence: float  # Overall confidence in analysis
```
 
---
 
## Workflow State Machine
 
```
                              ┌─────────────────────┐
                              │   Message Received  │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │  Add :eyes: Reaction │
                              │  (Acknowledge)      │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │ Contains Traceback? │
                              └──────────┬──────────┘
                                         │
                         ┌───────────────┴───────────────┐
                         │ No                         Yes│
                         ▼                               ▼
              ┌─────────────────────┐       ┌─────────────────────┐
              │  Remove Reaction    │       │   Parse Traceback   │
              │  (Silent Ignore)    │       └──────────┬──────────┘
              └─────────────────────┘                  │
                                                       ▼
                                          ┌─────────────────────┐
                                          │  Identify Repository │
                                          │  (from config/msg)  │
                                          └──────────┬──────────┘
                                                     │
                                                     ▼
                                          ┌─────────────────────┐
                                          │  Search Existing    │
                                          │  Issues             │
                                          └──────────┬──────────┘
                                                     │
                                  ┌──────────────────┴──────────────────┐
                                  │                                     │
                        Match Found (≥threshold)               No Match Found
                                  │                                     │
                                  ▼                                     ▼
                   ┌─────────────────────────┐          ┌─────────────────────────┐
                   │  Calculate Confidence   │          │  Clone Repository       │
                   │  Score                  │          │  (if not cached)        │
                   └───────────┬─────────────┘          └───────────┬─────────────┘
                               │                                    │
                   ┌───────────┴───────────┐                        ▼
                   │                       │           ┌─────────────────────────┐
         High Confidence          Low Confidence       │  Extract Code Context   │
           (≥0.85)                  (<0.85)            │  for Stack Frames       │
                   │                       │           └───────────┬─────────────┘
                   ▼                       │                       │
    ┌──────────────────────┐               │                       ▼
    │ Reply: Link to       │               │          ┌─────────────────────────┐
    │ Existing Issue       │               │          │  LLM: Analyze Error     │
    └──────────────────────┘               │          │  & Generate Fix         │
                                           │          └───────────┬─────────────┘
                                           │                      │
                                           │                      ▼
                                           │         ┌─────────────────────────┐
                                           │         │  LLM: Generate Issue    │
                                           │         │  Title & Body           │
                                           │         └───────────┬─────────────┘
                                           │                     │
                                           │                     ▼
                                           │         ┌─────────────────────────┐
                                           └────────►│  Create GitHub Issue    │
                                                     │  (via gh CLI)           │
                                                     └───────────┬─────────────┘
                                                                 │
                                                                 ▼
                                                    ┌─────────────────────────┐
                                                    │  Reply: Link to New     │
                                                    │  Issue + Summary        │
                                                    └───────────┬─────────────┘
                                                                │
                                                                ▼
                                                    ┌─────────────────────────┐
                                                    │  Update Reaction        │
                                                    │  :eyes: → :white_check_mark:     │
                                                    └─────────────────────────┘
```
 
### State Definitions
 
| State | Description | Transitions |
|-------|-------------|-------------|
| `IDLE` | Waiting for messages | → `RECEIVED` on new message |
| `RECEIVED` | Message received, not yet processed | → `PARSING` |
| `PARSING` | Extracting traceback from message | → `NO_TRACEBACK` or `SEARCHING` |
| `NO_TRACEBACK` | No traceback found, ignoring | → `IDLE` |
| `SEARCHING` | Searching for existing issues | → `MATCHED` or `ANALYZING` |
| `MATCHED` | Found existing issue | → `REPLYING` |
| `ANALYZING` | Cloning repo, running LLM analysis | → `CREATING` |
| `CREATING` | Creating new GitHub issue | → `REPLYING` |
| `REPLYING` | Sending reply to chat | → `IDLE` |
| `ERROR` | Error occurred during processing | → `IDLE` (after error reply) |
 
---
 
## Dependencies
 
```toml
# pyproject.toml
 
[project]
name = "ai-issue-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    # Core async runtime
    "asyncio-atexit>=1.0.1",        # Proper async cleanup on shutdown
 
    # Chat platform integrations
    "slack-bolt>=1.18.0",            # Slack Bot SDK (async support)
    "aiohttp>=3.9.0",                # Async HTTP for Slack
 
    # Configuration
    "pydantic>=2.5.0",               # Data validation and settings
    "pydantic-settings>=2.1.0",      # Environment variable handling
    "pyyaml>=6.0.1",                 # YAML configuration files
 
    # LLM providers
    "openai>=1.6.0",                 # OpenAI API client
    "anthropic>=0.8.0",              # Anthropic API client
    "httpx>=0.26.0",                 # Async HTTP for Ollama
 
    # Utilities
    "structlog>=24.1.0",             # Structured logging
    "tenacity>=8.2.0",               # Retry logic with backoff
    "cachetools>=5.3.0",             # In-memory caching (repo clones)
]
 
[project.optional-dependencies]
dev = [
    # Testing
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",        # Async test support
    "pytest-cov>=4.1.0",             # Coverage reporting
    "pytest-mock>=3.12.0",           # Mocking utilities
    "respx>=0.20.0",                 # Mock httpx requests
    "pytest-timeout>=2.2.0",         # Test timeouts
 
    # Type checking
    "mypy>=1.8.0",
    "types-PyYAML>=6.0.0",
 
    # Linting/Formatting
    "ruff>=0.1.9",                   # Fast linter + formatter
 
    # Development utilities
    "pre-commit>=3.6.0",
    "ipython>=8.19.0",               # Interactive debugging
]
 
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --tb=short"
 
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true
 
[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
```
 
### Dependency Purposes
 
| Package | Purpose |
|---------|---------|
| `slack-bolt` | Official Slack SDK with async support, handles WebSocket connections, events, and message formatting |
| `pydantic` | Data validation for models, automatic parsing of config files and API responses |
| `pydantic-settings` | Load configuration from environment variables with validation |
| `pyyaml` | Parse YAML configuration files |
| `openai` | Official OpenAI Python client with async support |
| `anthropic` | Official Anthropic Python client with async support |
| `httpx` | Modern async HTTP client for Ollama API calls |
| `structlog` | Structured logging with context, better than stdlib logging for observability |
| `tenacity` | Retry decorator with exponential backoff for resilient API calls |
| `cachetools` | LRU cache for repository clones and issue search results |
 
---
 
## Configuration Schema
 
```yaml
# config/config.example.yaml
 
# =============================================================================
# AI Issue Agent Configuration
# =============================================================================
# Environment variables can be referenced as ${VAR_NAME}
# Required variables are marked with [REQUIRED]
 
# -----------------------------------------------------------------------------
# Chat Platform Configuration
# -----------------------------------------------------------------------------
chat:
  # Provider: "slack" | "discord" | "teams"
  provider: slack
 
  slack:
    # [REQUIRED] Bot OAuth token (xoxb-...)
    bot_token: ${SLACK_BOT_TOKEN}
 
    # [REQUIRED] App-level token for Socket Mode (xapp-...)
    app_token: ${SLACK_APP_TOKEN}
 
    # Channels to monitor (by ID or name)
    # If empty, monitors all channels the bot is invited to
    channels:
      - "#errors"
      - "#production-alerts"
 
    # Reaction to add when processing starts
    processing_reaction: "eyes"
 
    # Reaction to add when processing completes
    complete_reaction: "white_check_mark"
 
    # Reaction to add on error
    error_reaction: "x"
 
# -----------------------------------------------------------------------------
# Version Control System Configuration
# -----------------------------------------------------------------------------
vcs:
  # Provider: "github" | "gitlab" | "bitbucket"
  provider: github
 
  github:
    # Default repository if not detected from message/channel
    default_repo: "myorg/myproject"
 
    # Directory for cloning repositories
    clone_dir: "/tmp/ai-issue-agent/repos"
 
    # Maximum age of cached clones before refresh (seconds)
    clone_cache_ttl: 3600
 
    # Labels to add to created issues
    default_labels:
      - "auto-triaged"
      - "needs-review"
 
    # gh CLI path (if not in PATH)
    gh_path: null
 
  # Channel-to-repository mapping
  # Maps chat channels to specific repositories
  channel_repos:
    "#frontend-errors": "myorg/frontend"
    "#backend-errors": "myorg/backend"
    "#infra-alerts": "myorg/infrastructure"
 
# -----------------------------------------------------------------------------
# LLM Provider Configuration
# -----------------------------------------------------------------------------
llm:
  # Provider: "openai" | "anthropic" | "ollama"
  provider: anthropic
 
  openai:
    api_key: ${OPENAI_API_KEY}
    model: "gpt-4-turbo-preview"
    max_tokens: 4096
    temperature: 0.3
 
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    model: "claude-3-sonnet-20240229"
    max_tokens: 4096
    temperature: 0.3
 
  ollama:
    base_url: "http://localhost:11434"
    model: "llama2:70b"
    timeout: 120
 
# -----------------------------------------------------------------------------
# Issue Matching Configuration
# -----------------------------------------------------------------------------
matching:
  # Minimum confidence score to consider an issue a match (0.0 - 1.0)
  confidence_threshold: 0.85
 
  # Maximum number of issues to search
  max_search_results: 20
 
  # Search in closed issues too?
  include_closed: true
 
  # How long to cache search results (seconds)
  search_cache_ttl: 300
 
  # Weights for different matching criteria
  weights:
    exception_type: 0.3
    exception_message: 0.4
    stack_frames: 0.2
    semantic_similarity: 0.1
 
# -----------------------------------------------------------------------------
# Code Analysis Configuration
# -----------------------------------------------------------------------------
analysis:
  # Lines of context to extract around error location
  context_lines: 15
 
  # Maximum files to analyze per traceback
  max_files: 10
 
  # Skip frames from these paths (stdlib, site-packages)
  skip_paths:
    - "/usr/lib/python"
    - "site-packages"
    - "<frozen"
 
  # Include these additional files if present
  include_files:
    - "README.md"
    - "pyproject.toml"
 
# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  format: json  # json or console
 
  # Log to file?
  file:
    enabled: false
    path: "/var/log/ai-issue-agent/agent.log"
    rotation: "10 MB"
    retention: 7  # days
 
# -----------------------------------------------------------------------------
# Runtime Configuration
# -----------------------------------------------------------------------------
runtime:
  # Maximum concurrent message processing
  max_concurrent: 5
 
  # Timeout for entire message processing pipeline (seconds)
  processing_timeout: 300
 
  # Retry configuration for transient failures
  retry:
    max_attempts: 3
    initial_delay: 1.0
    max_delay: 30.0
    exponential_base: 2.0
```
 
### Configuration Pydantic Schema
 
```python
# src/ai_issue_agent/config/schema.py
 
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from typing import Optional, Literal
from pathlib import Path
 
class SlackConfig(BaseModel):
    bot_token: str
    app_token: str
    channels: list[str] = []
    processing_reaction: str = "eyes"
    complete_reaction: str = "white_check_mark"
    error_reaction: str = "x"
 
class GitHubConfig(BaseModel):
    default_repo: str
    clone_dir: Path = Path("/tmp/ai-issue-agent/repos")
    clone_cache_ttl: int = 3600
    default_labels: list[str] = ["auto-triaged"]
    gh_path: Optional[str] = None
 
class OpenAIConfig(BaseModel):
    api_key: str
    model: str = "gpt-4-turbo-preview"
    max_tokens: int = 4096
    temperature: float = 0.3
 
class AnthropicConfig(BaseModel):
    api_key: str
    model: str = "claude-3-sonnet-20240229"
    max_tokens: int = 4096
    temperature: float = 0.3
 
class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "llama2:70b"
    timeout: int = 120
 
class MatchingConfig(BaseModel):
    confidence_threshold: float = Field(0.85, ge=0.0, le=1.0)
    max_search_results: int = 20
    include_closed: bool = True
    search_cache_ttl: int = 300
 
class AnalysisConfig(BaseModel):
    context_lines: int = 15
    max_files: int = 10
    skip_paths: list[str] = ["/usr/lib/python", "site-packages"]
    include_files: list[str] = ["README.md"]
 
class ChatConfig(BaseModel):
    provider: Literal["slack", "discord", "teams"]
    slack: Optional[SlackConfig] = None
 
class VCSConfig(BaseModel):
    provider: Literal["github", "gitlab", "bitbucket"]
    github: Optional[GitHubConfig] = None
    channel_repos: dict[str, str] = {}
 
class LLMConfig(BaseModel):
    provider: Literal["openai", "anthropic", "ollama"]
    openai: Optional[OpenAIConfig] = None
    anthropic: Optional[AnthropicConfig] = None
    ollama: Optional[OllamaConfig] = None
 
class AgentConfig(BaseSettings):
    chat: ChatConfig
    vcs: VCSConfig
    llm: LLMConfig
    matching: MatchingConfig = MatchingConfig()
    analysis: AnalysisConfig = AnalysisConfig()
 
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
```
 
---
 
## Edge Cases and Error Handling
 
### Edge Cases
 
| Category | Edge Case | Handling Strategy |
|----------|-----------|-------------------|
| **Parsing** | Traceback in code block (```) | Strip markdown fences before parsing |
| **Parsing** | Truncated traceback (Slack limit) | Parse what's available, note incompleteness in issue |
| **Parsing** | Multiple tracebacks in one message | Process each separately, create multiple issues |
| **Parsing** | Non-Python traceback (Java, Node) | Detect and skip with appropriate message |
| **Parsing** | Chained exceptions (`raise ... from ...`) | Parse all, link in issue body |
| **Parsing** | SyntaxError (different format) | Special case parser for syntax errors |
| **Matching** | Issue exists but is closed | Link to closed issue, optionally suggest reopening |
| **Matching** | Multiple issues match | Link to best match, mention others |
| **Matching** | Rate limited by GitHub search | Exponential backoff, queue messages |
| **Analysis** | Repository is private | Ensure `gh` is authenticated, handle auth errors |
| **Analysis** | File in traceback doesn't exist | Note missing file, analyze available files |
| **Analysis** | Very large files | Truncate to relevant sections |
| **Analysis** | Binary files referenced | Skip binary files |
| **LLM** | Token limit exceeded | Truncate context intelligently |
| **LLM** | Provider rate limit | Queue requests, exponential backoff |
| **LLM** | Provider timeout | Retry with smaller context |
| **LLM** | Hallucinated fix | Include confidence scores, mark as suggestions |
| **Chat** | Bot mentioned in thread | Process entire thread context |
| **Chat** | Duplicate messages (retries) | Idempotency via message ID tracking |
| **Chat** | Bot lacks channel access | Log warning, skip message |
| **General** | Network partition | Retry with backoff, alert on persistent failure |
| **General** | Partial completion | Track state, allow resume |
 
### Error Handling Strategy
 
```python
# src/ai_issue_agent/utils/async_helpers.py
 
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import httpx
 
# Retry decorator for API calls
api_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
)
 
# Custom exceptions
class AgentError(Exception):
    """Base exception for all agent errors."""
    pass
 
class TracebackParseError(AgentError):
    """Failed to parse traceback from message."""
    pass
 
class IssueSearchError(AgentError):
    """Failed to search for existing issues."""
    pass
 
class IssueCreateError(AgentError):
    """Failed to create new issue."""
    pass
 
class LLMAnalysisError(AgentError):
    """LLM analysis failed."""
    pass
 
class RateLimitError(AgentError):
    """Rate limit exceeded."""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
```
 
### Error Recovery Flow
 
```
┌─────────────────┐
│  Error Occurs   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      Yes     ┌─────────────────┐
│  Retryable?     ├─────────────►│  Retry with     │
│                 │              │  Backoff        │
└────────┬────────┘              └────────┬────────┘
         │ No                             │
         │                                │ Max retries?
         ▼                                ▼ Yes
┌─────────────────┐              ┌─────────────────┐
│  Log Error      │◄─────────────┤  Give Up        │
│  (Structured)   │              └─────────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Reply with     │
│  Error Message  │
│  (User-friendly)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Add :x:        │
│  Reaction       │
└─────────────────┘
```
 
---
 
## Testing Strategy
 
### Test Pyramid
 
```
                    ┌─────────────┐
                    │    E2E      │  ~10% of tests
                    │   Tests     │  Full workflow with real services
                    └──────┬──────┘
                           │
                ┌──────────┴──────────┐
                │    Integration      │  ~30% of tests
                │       Tests         │  Component interactions
                └──────────┬──────────┘
                           │
         ┌─────────────────┴─────────────────┐
         │            Unit Tests             │  ~60% of tests
         │    Individual functions/classes   │
         └───────────────────────────────────┘
```
 
### Unit Tests
 
**TracebackParser Tests** (`tests/unit/test_traceback_parser.py`)
```python
class TestTracebackParser:
    """Test traceback parsing functionality."""
 
    def test_parse_simple_traceback(self): ...
    def test_parse_traceback_in_code_block(self): ...
    def test_parse_chained_exception(self): ...
    def test_parse_syntax_error(self): ...
    def test_parse_multiline_exception_message(self): ...
    def test_contains_traceback_positive(self): ...
    def test_contains_traceback_negative(self): ...
    def test_normalize_file_paths(self): ...
    def test_extract_multiple_tracebacks(self): ...
    def test_handle_truncated_traceback(self): ...
```
 
**IssueMatcher Tests** (`tests/unit/test_issue_matcher.py`)
```python
class TestIssueMatcher:
    """Test issue matching logic."""
 
    def test_build_search_query(self): ...
    def test_calculate_similarity_exact_match(self): ...
    def test_calculate_similarity_partial_match(self): ...
    def test_calculate_similarity_no_match(self): ...
    def test_filter_closed_issues(self): ...
    def test_rank_matches_by_confidence(self): ...
```
 
**Configuration Tests** (`tests/unit/test_config.py`)
```python
class TestConfigLoader:
    """Test configuration loading and validation."""
 
    def test_load_yaml_config(self): ...
    def test_env_var_substitution(self): ...
    def test_missing_required_field(self): ...
    def test_invalid_provider(self): ...
    def test_default_values(self): ...
```
 
### Integration Tests
 
**Slack Adapter Tests** (`tests/integration/test_slack_adapter.py`)
```python
class TestSlackAdapter:
    """Test Slack integration with mocked Slack API."""
 
    @pytest.fixture
    def mock_slack_client(self): ...
 
    async def test_send_reply(self): ...
    async def test_send_threaded_reply(self): ...
    async def test_add_reaction(self): ...
    async def test_handle_rate_limit(self): ...
    async def test_reconnect_on_disconnect(self): ...
```
 
**GitHub Adapter Tests** (`tests/integration/test_github_adapter.py`)
```python
class TestGitHubAdapter:
    """Test GitHub integration with mocked gh CLI."""
 
    @pytest.fixture
    def mock_gh_cli(self): ...
 
    async def test_search_issues(self): ...
    async def test_create_issue(self): ...
    async def test_clone_repository(self): ...
    async def test_get_file_content(self): ...
    async def test_handle_auth_error(self): ...
```
 
**LLM Adapter Tests** (`tests/integration/test_llm_adapters.py`)
```python
class TestLLMAdapters:
    """Test LLM integrations with mocked APIs."""
 
    @pytest.fixture
    def mock_openai(self): ...
 
    @pytest.fixture
    def mock_anthropic(self): ...
 
    async def test_analyze_error_openai(self): ...
    async def test_analyze_error_anthropic(self): ...
    async def test_generate_issue_body(self): ...
    async def test_handle_token_limit(self): ...
    async def test_handle_rate_limit(self): ...
```
 
### End-to-End Tests
 
**Full Workflow Tests** (`tests/e2e/test_full_workflow.py`)
```python
class TestFullWorkflow:
    """Test complete message processing workflows."""
 
    @pytest.fixture
    async def running_agent(self):
        """Start agent with test configuration."""
        ...
 
    async def test_process_traceback_create_new_issue(self): ...
    async def test_process_traceback_link_existing_issue(self): ...
    async def test_ignore_non_traceback_message(self): ...
    async def test_handle_network_failure(self): ...
    async def test_handle_concurrent_messages(self): ...
```
 
### Test Fixtures
 
```python
# tests/conftest.py
 
import pytest
from pathlib import Path
 
@pytest.fixture
def sample_traceback() -> str:
    """Load sample traceback from fixtures."""
    return (Path(__file__).parent / "fixtures/tracebacks/simple.txt").read_text()
 
@pytest.fixture
def parsed_traceback(sample_traceback) -> ParsedTraceback:
    """Pre-parsed traceback for tests."""
    return TracebackParser().parse(sample_traceback)
 
@pytest.fixture
def mock_config() -> AgentConfig:
    """Test configuration with mock values."""
    return AgentConfig(
        chat=ChatConfig(provider="slack", slack=SlackConfig(...)),
        vcs=VCSConfig(provider="github", github=GitHubConfig(...)),
        llm=LLMConfig(provider="anthropic", anthropic=AnthropicConfig(...)),
    )
 
@pytest.fixture
def mock_vcs_provider():
    """Mock VCS provider for isolated tests."""
    return AsyncMock(spec=VCSProvider)
```
 
### Test Fixtures Files
 
```
tests/fixtures/
├── tracebacks/
│   ├── simple.txt           # Basic ValueError traceback
│   ├── nested.txt           # Chained exception
│   ├── syntax_error.txt     # SyntaxError format
│   ├── multiline_msg.txt    # Multi-line exception message
│   ├── in_code_block.txt    # Traceback wrapped in ```
│   └── truncated.txt        # Incomplete traceback
└── issues/
    ├── sample_issues.json   # Mock GitHub issues for matching
    └── search_results.json  # Mock search API responses
```
 
### Coverage Requirements
 
- **Minimum overall coverage**: 80%
- **Core modules coverage**: 90%+
- **Adapter modules coverage**: 75%+
 
### CI Pipeline Stages
 
```yaml
# .github/workflows/ci.yml stages
stages:
  - lint:
      - ruff check
      - ruff format --check
      - mypy
  - test:
      - pytest tests/unit --cov
      - pytest tests/integration --cov
  - e2e (on main only):
      - pytest tests/e2e
```
 
---
 
## Appendix: Prompt Templates for LLM
 
### Error Analysis Prompt
 
```
You are analyzing a Python error to identify its root cause and suggest fixes.
 
## Traceback
```
{traceback}
```
 
## Code Context
{code_context}
 
## Task
1. Identify the root cause of this error
2. Explain why this error occurred
3. Suggest one or more fixes with code examples
4. Rate your confidence (0.0-1.0) in each suggestion
 
## Response Format
Respond in JSON:
{
  "root_cause": "Brief description",
  "explanation": "Detailed explanation",
  "suggested_fixes": [
    {
      "description": "What this fix does",
      "file_path": "path/to/file.py",
      "original_code": "...",
      "fixed_code": "...",
      "confidence": 0.9
    }
  ],
  "severity": "low|medium|high|critical",
  "related_docs": ["https://docs.python.org/..."]
}
```
 
### Issue Body Generation Prompt
 
```
Generate a clear, well-formatted GitHub issue body for this error.
 
## Error Information
- Exception: {exception_type}: {exception_message}
- File: {file_path}:{line_number}
- Function: {function_name}
 
## Analysis
{analysis}
 
## Requirements
- Use Markdown formatting
- Include the traceback in a code block
- Add a "Suggested Fix" section
- Keep it concise but complete
```
 
---
 
## Next Steps
 
After this architecture is approved:
 
1. **Phase 1: Core Infrastructure**
   - Set up project structure and dependencies
   - Implement configuration loading
   - Create abstract interfaces
 
2. **Phase 2: Traceback Parsing**
   - Implement TracebackParser with tests
   - Handle all traceback formats
 
3. **Phase 3: Adapters**
   - Implement Slack adapter
   - Implement GitHub adapter (gh CLI wrapper)
   - Implement one LLM adapter (Anthropic recommended)
 
4. **Phase 4: Core Logic**
   - Implement IssueMatcher
   - Implement CodeAnalyzer
   - Implement MessageHandler
 
5. **Phase 5: Integration**
   - Wire up Agent orchestrator
   - End-to-end testing
   - Documentation
 
6. **Phase 6: Additional Adapters**
   - OpenAI adapter
   - Ollama adapter
   - (Future) Discord, GitLab, etc.
