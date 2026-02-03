# Implementation Plan

This document outlines the phased implementation plan for AI Issue Agent.

## Overview

The implementation is divided into 6 phases, progressing from foundational infrastructure to full integration. Each phase builds on the previous, with clear deliverables and acceptance criteria.

---

## Phase 1: Project Setup & Core Infrastructure

**Goal:** Establish project structure, dependencies, and foundational utilities.

### 1.1 Project Scaffolding
- Create directory structure as defined in ARCHITECTURE.md
- Set up `pyproject.toml` with all dependencies
- Configure `ruff`, `mypy`, and `pytest`
- Create `config/config.example.yaml`
- Set up pre-commit hooks

### 1.2 Security Utilities
- Implement `SecretRedactor` class with all patterns from SECURITY.md
- Implement input validation functions (`validate_repo_name`, `sanitize_for_shell`)
- Implement `SafeGHCli` wrapper for subprocess calls
- Implement log sanitization utilities
- **Tests:** 90%+ coverage on security module

### 1.3 Async Helpers
- Implement retry decorator with tenacity
- Implement rate limiter class
- Implement timeout utilities
- **Tests:** Unit tests for all helpers

### 1.4 CI/CD Pipeline
- Create `.github/workflows/ci.yml`
- Configure lint, security scan, test stages
- Set up code coverage reporting

**Acceptance Criteria:**
- [ ] `pip install -e .` works
- [ ] `ruff check` and `mypy` pass
- [ ] `pytest tests/unit/test_security.py` passes with 90%+ coverage
- [ ] CI pipeline runs on PR

---

## Phase 2: Data Models & Interfaces

**Goal:** Define all data structures and abstract interfaces.

### 2.1 Data Models
- Implement `models/traceback.py` (StackFrame, ParsedTraceback)
- Implement `models/issue.py` (Issue, IssueSearchResult, IssueCreate, IssueMatch)
- Implement `models/message.py` (ChatMessage, ChatReply, ProcessingResult)
- Implement `models/analysis.py` (CodeContext, SuggestedFix, ErrorAnalysis)
- **Tests:** Unit tests for model properties and methods

### 2.2 Abstract Interfaces
- Implement `interfaces/chat.py` (ChatProvider protocol)
- Implement `interfaces/vcs.py` (VCSProvider protocol)
- Implement `interfaces/llm.py` (LLMProvider protocol)
- **Tests:** Protocol compliance tests

### 2.3 Configuration Schema
- Implement `config/schema.py` with all Pydantic models and validators
- Implement `config/loader.py` for YAML + env var loading
- **Tests:** Config validation tests, including security validators

**Acceptance Criteria:**
- [ ] All models are immutable (frozen dataclasses)
- [ ] All interfaces use `typing.Protocol`
- [ ] Config validators reject invalid repo names, SSRF URLs
- [ ] 90%+ coverage on models and config

---

## Phase 3: Traceback Parser

**Goal:** Implement robust Python traceback parsing.

### 3.1 Core Parser
- Implement `TracebackParser.contains_traceback()`
- Implement `TracebackParser.parse()` for standard tracebacks
- Implement `TracebackParser.extract_all()` for multiple/chained exceptions

### 3.2 Edge Cases
- Handle tracebacks in markdown code blocks
- Handle SyntaxError format (different structure)
- Handle truncated tracebacks
- Handle multi-line exception messages
- Handle chained exceptions (`raise ... from ...`)

### 3.3 Path Normalization
- Implement `StackFrame.normalized_path`
- Implement `StackFrame.is_stdlib` and `is_site_packages`
- Filter out non-project frames

**Acceptance Criteria:**
- [ ] Parses all fixture files in `tests/fixtures/tracebacks/`
- [ ] Correctly identifies project vs stdlib frames
- [ ] 95%+ coverage on parser module

---

## Phase 4: Adapters

**Goal:** Implement concrete adapters for Slack, GitHub, and Anthropic.

### 4.1 GitHub Adapter (VCS)
- Implement `GitHubAdapter` using `SafeGHCli`
- Implement `search_issues()` with query building
- Implement `get_issue()` and `create_issue()`
- Implement `clone_repository()` with security controls
- Implement `get_file_content()` and `get_default_branch()`
- **Tests:** Integration tests with mocked `gh` CLI

### 4.2 Slack Adapter (Chat)
- Implement `SlackAdapter` using `slack-bolt`
- Implement `connect()` and `disconnect()`
- Implement `listen()` as async generator
- Implement `send_reply()` with threading support
- Implement `add_reaction()` and `remove_reaction()`
- **Tests:** Integration tests with mocked Slack client

### 4.3 Anthropic Adapter (LLM)
- Implement `AnthropicAdapter` with structured prompts
- Implement `analyze_error()` with output validation
- Implement `generate_issue_body()` and `generate_issue_title()`
- Implement `calculate_similarity()` for issue matching
- Apply `SecretRedactor` before all LLM calls
- **Tests:** Integration tests with mocked API responses

**Acceptance Criteria:**
- [ ] All adapters implement their respective protocols
- [ ] GitHub adapter validates all inputs
- [ ] LLM adapter validates all outputs against schema
- [ ] Secret redaction applied before external calls
- [ ] 80%+ coverage on adapter modules

---

## Phase 5: Core Business Logic

**Goal:** Implement the core processing pipeline.

### 5.1 Issue Matcher
- Implement query building from parsed tracebacks
- Implement multi-strategy matching (exact, similar, semantic)
- Implement confidence scoring and ranking
- **Tests:** Unit tests with mock issues

### 5.2 Code Analyzer
- Implement repository cloning with cache management
- Implement code context extraction for stack frames
- Implement intelligent context truncation for LLM limits
- **Tests:** Integration tests with sample repos

### 5.3 Message Handler
- Implement the full processing pipeline
- Implement decision logic (link vs create)
- Implement reply formatting
- Implement state tracking for observability
- **Tests:** Unit tests with mocked dependencies

### 5.4 Agent Orchestrator
- Implement `Agent.start()` and `Agent.stop()`
- Implement concurrent message processing with semaphore
- Implement graceful shutdown handling
- Wire up all components
- **Tests:** Integration tests for lifecycle

**Acceptance Criteria:**
- [ ] Full workflow executes: message → parse → match/create → reply
- [ ] Concurrent processing respects `max_concurrent` limit
- [ ] Graceful shutdown completes in-flight requests
- [ ] 90%+ coverage on core modules

---

## Phase 6: Integration & Polish

**Goal:** End-to-end testing, documentation, and additional adapters.

### 6.1 End-to-End Tests
- Implement full workflow test with real (sandboxed) services
- Test error recovery scenarios
- Test rate limiting behavior
- Test duplicate detection

### 6.2 Additional LLM Adapters
- Implement `OpenAIAdapter`
- Implement `OllamaAdapter` with SSRF protection
- **Tests:** Integration tests for each

### 6.3 Documentation & Deployment
- Create `docs/DEPLOYMENT.md` with setup instructions
- Create `docs/DEVELOPMENT.md` with contributor guide
- Update README with usage examples
- Create Docker configuration (optional)

### 6.4 Observability
- Implement structured logging throughout
- Add metrics collection points
- Create health check endpoint

**Acceptance Criteria:**
- [ ] E2E tests pass
- [ ] All three LLM providers work
- [ ] Documentation complete
- [ ] 80%+ overall coverage

---

## GitHub Issues

All issues have been created and can be tracked at: https://github.com/jtdub/ai-issue-agent/issues

| Phase | Issue | Title | Priority |
|-------|-------|-------|----------|
| 1 | [#1](https://github.com/jtdub/ai-issue-agent/issues/1) | Project scaffolding and pyproject.toml setup | P0 |
| 1 | [#2](https://github.com/jtdub/ai-issue-agent/issues/2) | Implement security utilities (SecretRedactor, input validation) | P0 |
| 1 | [#3](https://github.com/jtdub/ai-issue-agent/issues/3) | Implement async helpers (retry, rate limiting, timeouts) | P1 |
| 1 | [#4](https://github.com/jtdub/ai-issue-agent/issues/4) | Set up CI/CD pipeline | P1 |
| 2 | [#5](https://github.com/jtdub/ai-issue-agent/issues/5) | Implement data models (traceback, issue, message, analysis) | P0 |
| 2 | [#6](https://github.com/jtdub/ai-issue-agent/issues/6) | Implement abstract interfaces (ChatProvider, VCSProvider, LLMProvider) | P0 |
| 2 | [#7](https://github.com/jtdub/ai-issue-agent/issues/7) | Implement configuration system with security validators | P0 |
| 3 | [#8](https://github.com/jtdub/ai-issue-agent/issues/8) | Implement TracebackParser | P0 |
| 4 | [#9](https://github.com/jtdub/ai-issue-agent/issues/9) | Implement GitHub adapter (VCSProvider) | P0 |
| 4 | [#10](https://github.com/jtdub/ai-issue-agent/issues/10) | Implement Slack adapter (ChatProvider) | P0 |
| 4 | [#11](https://github.com/jtdub/ai-issue-agent/issues/11) | Implement Anthropic LLM adapter | P0 |
| 5 | [#12](https://github.com/jtdub/ai-issue-agent/issues/12) | Implement IssueMatcher | P1 |
| 5 | [#13](https://github.com/jtdub/ai-issue-agent/issues/13) | Implement CodeAnalyzer | P1 |
| 5 | [#14](https://github.com/jtdub/ai-issue-agent/issues/14) | Implement MessageHandler (processing pipeline) | P0 |
| 5 | [#15](https://github.com/jtdub/ai-issue-agent/issues/15) | Implement Agent orchestrator | P0 |
| 6 | [#16](https://github.com/jtdub/ai-issue-agent/issues/16) | Implement end-to-end tests | P1 |
| 6 | [#17](https://github.com/jtdub/ai-issue-agent/issues/17) | Implement OpenAI LLM adapter | P2 |
| 6 | [#18](https://github.com/jtdub/ai-issue-agent/issues/18) | Implement Ollama LLM adapter (local models) | P2 |
| 6 | [#19](https://github.com/jtdub/ai-issue-agent/issues/19) | Create deployment and development documentation | P2 |
| 6 | [#20](https://github.com/jtdub/ai-issue-agent/issues/20) | Implement observability (structured logging, metrics) | P2 |

### Priority Order

1. **P0 (Critical Path):** #1, #2, #5, #6, #7, #8, #9, #10, #11, #14, #15
2. **P1 (Important):** #3, #4, #12, #13, #16
3. **P2 (Nice to Have):** #17, #18, #19, #20

### Dependencies

```
#1 ─┬─► #2 ─┬─► #5 ─► #6 ─► #7
    │       │
    │       └─► #3
    │
    └─► #4

#7 ─┬─► #8 (TracebackParser)
    │
    ├─► #9 (GitHub) ─┬─► #12 (IssueMatcher)
    │                └─► #13 (CodeAnalyzer)
    │
    ├─► #10 (Slack)
    │
    └─► #11 (Anthropic LLM)

#9 + #10 + #11 + #12 + #13 ─► #14 (MessageHandler) ─► #15 (Agent) ─► #16 (E2E)

#15 ─► #17 (OpenAI)
#15 ─► #18 (Ollama)
#15 ─► #19 (Docs)
#15 ─► #20 (Observability)
```

---

## Timeline Estimates

Not providing time estimates per project guidelines. Work should be done in priority order, with each phase completing before the next begins (except where parallelization is possible per the dependency graph).
