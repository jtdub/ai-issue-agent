# Core Components Guide

This document provides detailed documentation for the core business logic components
of the AI Issue Agent.

## Overview

The core components implement the main business logic for processing chat messages,
detecting tracebacks, matching issues, and creating new issues. These components are
provider-agnostic and work with any combination of chat, VCS, and LLM adapters.

## Components

### Agent (`core/agent.py`)

The `Agent` class is the main orchestrator that coordinates all components and manages
the application lifecycle.

#### Key Responsibilities

- Initialize and manage adapter instances
- Route incoming messages through the processing pipeline
- Handle graceful startup and shutdown
- Manage concurrent message processing with configurable limits

#### Usage

```python
from ai_issue_agent.core import Agent, create_agent
from ai_issue_agent.config.loader import load_config

# Load configuration
config = load_config("config/config.yaml")

# Create agent with all dependencies
agent = await create_agent(config)

# Start processing messages
await agent.start()  # Blocks until shutdown signal
```

#### Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `max_concurrent` | int | 5 | Maximum concurrent message processing |
| `shutdown_timeout` | int | 30 | Timeout for graceful shutdown (seconds) |

#### Signal Handling

The agent registers handlers for `SIGTERM` and `SIGINT` to enable graceful shutdown:

1. Signals shutdown event
2. Waits for in-flight requests to complete (with timeout)
3. Disconnects from chat provider
4. Cleans up resources

---

### TracebackParser (`core/traceback_parser.py`)

The `TracebackParser` class detects and parses Python tracebacks from text.

#### Key Features

- Detects standard Python tracebacks
- Handles chained exceptions (`raise ... from ...`)
- Parses SyntaxError/IndentationError/TabError
- Extracts tracebacks from markdown code blocks
- Supports multi-line exception messages

#### Usage

```python
from ai_issue_agent.core import TracebackParser

parser = TracebackParser()

# Check if text contains a traceback
if parser.contains_traceback(message_text):
    # Parse the traceback
    traceback = parser.parse(message_text)
    
    print(f"Exception: {traceback.exception_type}")
    print(f"Message: {traceback.exception_message}")
    print(f"Frames: {len(traceback.frames)}")
```

#### Supported Formats

1. **Standard Traceback**
   ```
   Traceback (most recent call last):
     File "example.py", line 10, in main
       result = process()
   ValueError: invalid input
   ```

2. **Chained Exception**
   ```
   Traceback (most recent call last):
     ...
   ConnectionError: Failed to connect
   
   The above exception was the direct cause of the following exception:
   
   Traceback (most recent call last):
     ...
   DataLoadError: Failed to load data
   ```

3. **Syntax Error**
   ```
     File "broken.py", line 5
       def incomplete(
                      ^
   SyntaxError: unexpected EOF while parsing
   ```

---

### IssueMatcher (`core/issue_matcher.py`)

The `IssueMatcher` class finds existing issues that match a given traceback.

#### Matching Strategies

1. **Exact Match** (weight: 0.5)
   - Same exception type
   - Similar exception message terms

2. **Stack Trace Similarity** (weight: 0.3)
   - Overlapping file names
   - Matching function names

3. **Semantic Similarity** (weight: 0.2)
   - LLM-based comparison
   - Search relevance scoring

#### Usage

```python
from ai_issue_agent.core import IssueMatcher
from ai_issue_agent.config.schema import MatchingConfig

config = MatchingConfig(
    confidence_threshold=0.85,
    max_search_results=20,
    include_closed=True,
)

matcher = IssueMatcher(vcs_provider, llm_provider, config)

# Find matching issues
matches = await matcher.find_matches("owner/repo", traceback)

for match in matches:
    print(f"Issue #{match.issue.number}: {match.confidence:.2%}")
    print(f"Reasons: {', '.join(match.match_reasons)}")
```

#### Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `confidence_threshold` | float | 0.85 | Minimum confidence for match |
| `max_search_results` | int | 20 | Maximum issues to search |
| `include_closed` | bool | True | Include closed issues in search |
| `search_cache_ttl` | int | 300 | Cache TTL in seconds |

---

### CodeAnalyzer (`core/code_analyzer.py`)

The `CodeAnalyzer` class extracts code context from repositories for LLM analysis.

#### Key Features

- Clones repositories with caching
- Extracts surrounding code for stack frames
- Prevents path traversal attacks
- Applies secret redaction to extracted code
- Includes configurable additional files (e.g., README.md)

#### Usage

```python
from ai_issue_agent.core import CodeAnalyzer
from ai_issue_agent.config.schema import AnalysisConfig, GitHubConfig

analysis_config = AnalysisConfig(
    context_lines=15,
    max_files=10,
    include_files=["README.md"],
)

analyzer = CodeAnalyzer(vcs_provider, analysis_config, github_config)

# Extract code context for traceback
contexts = await analyzer.analyze("owner/repo", traceback)

for ctx in contexts:
    print(f"File: {ctx.file_path}")
    print(f"Lines {ctx.start_line}-{ctx.end_line}")
    print(ctx.content)
```

#### Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `context_lines` | int | 15 | Lines of context around error |
| `max_files` | int | 10 | Maximum files to analyze |
| `skip_paths` | list | ["/usr/lib/python", "site-packages"] | Paths to skip |
| `include_files` | list | ["README.md"] | Additional files to include |

#### Security

- **Path Traversal Prevention**: All file paths are validated
- **Secret Redaction**: Extracted code is automatically redacted
- **Shallow Clones**: Uses `--depth 1` for efficiency and security

---

### MessageHandler (`core/message_handler.py`)

The `MessageHandler` class orchestrates the complete message processing pipeline.

#### Pipeline Flow

```
Message Received
       │
       ▼
Add 👀 Reaction
       │
       ▼
Contains Traceback? ──No──► Remove Reaction ──► NO_TRACEBACK
       │
      Yes
       │
       ▼
Parse Traceback
       │
       ▼
Identify Repository
       │
       ▼
Search Existing Issues
       │
       ├─── Match Found (≥threshold)
       │         │
       │         ▼
       │    Reply with Link ──► EXISTING_ISSUE_LINKED
       │
       └─── No Match
               │
               ▼
         Clone Repository
               │
               ▼
         Extract Code Context
               │
               ▼
         LLM: Analyze Error
               │
               ▼
         LLM: Generate Issue
               │
               ▼
         Create GitHub Issue
               │
               ▼
         Reply with New Issue ──► NEW_ISSUE_CREATED
```

#### Usage

```python
from ai_issue_agent.core import MessageHandler
from ai_issue_agent.models.message import ProcessingResult

handler = MessageHandler(
    chat=chat_provider,
    vcs=vcs_provider,
    llm=llm_provider,
    parser=traceback_parser,
    matcher=issue_matcher,
    analyzer=code_analyzer,
    config=agent_config,
)

result = await handler.handle(message)

if result == ProcessingResult.NEW_ISSUE_CREATED:
    print("Created new issue!")
elif result == ProcessingResult.EXISTING_ISSUE_LINKED:
    print("Linked to existing issue!")
```

#### Processing Results

| Result | Description |
|--------|-------------|
| `NO_TRACEBACK` | No traceback detected in message |
| `EXISTING_ISSUE_LINKED` | Found and linked existing issue |
| `NEW_ISSUE_CREATED` | Created new GitHub issue |
| `ERROR` | Processing failed |

---

## Data Flow

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────┐
│ ChatMessage  │────►│ TracebackParser  │────►│ ParsedTrace │
└──────────────┘     └──────────────────┘     └─────────────┘
                                                     │
                     ┌──────────────────┐            │
                     │   IssueMatcher   │◄───────────┘
                     └──────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
        Match Found                  No Match
              │                           │
              ▼                           ▼
    ┌─────────────────┐         ┌──────────────┐
    │  IssueMatch     │         │ CodeAnalyzer │
    └─────────────────┘         └──────────────┘
              │                           │
              │                           ▼
              │                 ┌──────────────┐
              │                 │ LLMProvider  │
              │                 └──────────────┘
              │                           │
              ▼                           ▼
    ┌─────────────────┐         ┌──────────────┐
    │  Link to Issue  │         │ Create Issue │
    └─────────────────┘         └──────────────┘
```

## Error Handling

All core components follow these error handling principles:

1. **Fail-Closed**: Security-sensitive operations fail safely
2. **Graceful Degradation**: Partial failures don't crash the system
3. **Structured Logging**: All errors are logged with context
4. **User-Friendly Messages**: Error replies are informative but safe

### Exception Hierarchy

```
AgentError
├── TracebackParseError
├── IssueMatcherError
│   └── SearchError
├── CodeAnalyzerError
│   ├── CloneError
│   ├── FileReadError
│   └── PathTraversalError
└── MessageHandlerError
```

## Testing

Each component has comprehensive test coverage:

- **Unit Tests**: Test individual methods with mocked dependencies
- **Integration Tests**: Test component interactions
- **E2E Tests**: Test complete workflows

Run tests with:

```bash
pytest tests/unit/test_agent.py -v
pytest tests/unit/test_traceback_parser.py -v
pytest tests/unit/test_issue_matcher.py -v
pytest tests/unit/test_code_analyzer.py -v
pytest tests/unit/test_message_handler.py -v
```

## Best Practices

1. **Always use the factory function** for creating agents
2. **Configure appropriate timeouts** for your environment
3. **Monitor the stats property** for health checks
4. **Set up proper signal handlers** for containerized deployments
5. **Use structured logging** for observability
