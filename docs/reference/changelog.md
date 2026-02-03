# Changelog

All notable changes to AI Issue Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial documentation site with MkDocs
- User, Administrator, and Developer guides
- Comprehensive security documentation

## [0.1.0] - 2026-02-03

### Added
- Core project infrastructure
- Security utilities with secret redaction
- Safe subprocess wrappers for GitHub CLI
- Async helpers with retry logic and rate limiting
- CI/CD pipeline with GitHub Actions
- Comprehensive test suite (175+ tests, 82% coverage)
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
