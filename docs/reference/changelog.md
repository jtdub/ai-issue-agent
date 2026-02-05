# Changelog

All notable changes to AI Issue Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Core business logic components: IssueMatcher, CodeAnalyzer, MessageHandler, Agent
- IssueMatcher with 3 matching strategies (exact, similar stack trace, semantic similarity)
- CodeAnalyzer with repository cloning, TTL-based cache, and path traversal prevention
- MessageHandler orchestrating full processing pipeline with reaction management
- Agent orchestrator with concurrent message processing and graceful shutdown
- Health check system (`--health-check` CLI flag) with dependency validation
- Structured logging with secret sanitization (JSON and console formats)
- Metrics collection with Counter, Gauge, Histogram types and Prometheus export
- Initial documentation site with MkDocs
- User, Administrator, and Developer guides
- Comprehensive security documentation
- Core Components developer guide

## [0.1.0] - 2026-02-03

### Added
- Core project infrastructure
- Security utilities with secret redaction
- Safe subprocess wrappers for GitHub CLI
- Async helpers with retry logic and rate limiting
- CI/CD pipeline with GitHub Actions
- Comprehensive test suite (175+ tests, 80%+ coverage)
- Pre-commit hooks for code quality
- Configuration management with YAML and environment variables

### Security
- Automatic secret redaction for 30+ patterns
- Input validation to prevent injection attacks
- SSRF protection for LLM endpoints
- Fail-closed error handling
- Security documentation and threat model

## [0.0.1] - 2026-01-15

### Added
- Initial project setup
- Project structure and architecture
- Development environment configuration

---

[Unreleased]: https://github.com/jtdub/ai-issue-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jtdub/ai-issue-agent/releases/tag/v0.1.0
[0.0.1]: https://github.com/jtdub/ai-issue-agent/releases/tag/v0.0.1
