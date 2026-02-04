"""Data models for VCS issues."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class IssueState(Enum):
    """State of a VCS issue."""

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
