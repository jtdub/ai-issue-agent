"""Tests for issue data models."""

from datetime import datetime

import pytest

from ai_issue_agent.models.issue import (
    Issue,
    IssueCreate,
    IssueMatch,
    IssueSearchResult,
    IssueState,
)


class TestIssueState:
    """Test IssueState enum."""

    def test_issue_state_values(self):
        """Test IssueState enum values."""
        assert IssueState.OPEN.value == "open"
        assert IssueState.CLOSED.value == "closed"

    def test_issue_state_members(self):
        """Test IssueState has correct members."""
        assert set(IssueState) == {IssueState.OPEN, IssueState.CLOSED}


class TestIssue:
    """Test Issue dataclass."""

    def test_create_issue(self):
        """Test creating an Issue."""
        created = datetime(2024, 1, 1, 12, 0, 0)
        updated = datetime(2024, 1, 2, 14, 30, 0)

        issue = Issue(
            number=42,
            title="ValueError in data processing",
            body="Traceback shows...",
            url="https://github.com/owner/repo/issues/42",
            state=IssueState.OPEN,
            labels=("bug", "triage"),
            created_at=created,
            updated_at=updated,
            author="alice",
        )

        assert issue.number == 42
        assert issue.title == "ValueError in data processing"
        assert issue.body == "Traceback shows..."
        assert issue.url == "https://github.com/owner/repo/issues/42"
        assert issue.state == IssueState.OPEN
        assert issue.labels == ("bug", "triage")
        assert issue.created_at == created
        assert issue.updated_at == updated
        assert issue.author == "alice"

    def test_issue_with_empty_labels(self):
        """Test creating an issue with no labels."""
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

        assert issue.labels == ()
        assert len(issue.labels) == 0

    def test_issue_state_closed(self):
        """Test issue with closed state."""
        issue = Issue(
            number=1,
            title="Fixed bug",
            body="Body",
            url="https://example.com/1",
            state=IssueState.CLOSED,
            labels=(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="user",
        )

        assert issue.state == IssueState.CLOSED

    def test_labels_is_tuple(self):
        """Test that labels is a tuple (immutable)."""
        issue = Issue(
            number=1,
            title="Test",
            body="Body",
            url="https://example.com/1",
            state=IssueState.OPEN,
            labels=("bug", "enhancement"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="user",
        )

        assert isinstance(issue.labels, tuple)

    def test_frozen_immutable(self):
        """Test that Issue is frozen (immutable)."""
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

        with pytest.raises(AttributeError):
            issue.number = 99  # type: ignore


class TestIssueSearchResult:
    """Test IssueSearchResult dataclass."""

    def test_create_search_result(self):
        """Test creating a search result."""
        issue = Issue(
            number=42,
            title="Test Issue",
            body="Body",
            url="https://example.com/42",
            state=IssueState.OPEN,
            labels=(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="user",
        )

        result = IssueSearchResult(
            issue=issue,
            relevance_score=0.85,
            matched_terms=("ValueError", "data processing"),
        )

        assert result.issue == issue
        assert result.relevance_score == 0.85
        assert result.matched_terms == ("ValueError", "data processing")

    def test_matched_terms_is_tuple(self):
        """Test that matched_terms is a tuple."""
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

        result = IssueSearchResult(
            issue=issue, relevance_score=0.5, matched_terms=("term1", "term2")
        )

        assert isinstance(result.matched_terms, tuple)

    def test_frozen_immutable(self):
        """Test that IssueSearchResult is frozen."""
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

        result = IssueSearchResult(issue=issue, relevance_score=0.5, matched_terms=())

        with pytest.raises(AttributeError):
            result.relevance_score = 0.9  # type: ignore


class TestIssueCreate:
    """Test IssueCreate dataclass."""

    def test_create_with_all_fields(self):
        """Test creating IssueCreate with all fields."""
        issue_create = IssueCreate(
            title="New bug report",
            body="Description of the bug",
            labels=("bug", "needs-triage"),
            assignees=("alice", "bob"),
        )

        assert issue_create.title == "New bug report"
        assert issue_create.body == "Description of the bug"
        assert issue_create.labels == ("bug", "needs-triage")
        assert issue_create.assignees == ("alice", "bob")

    def test_create_with_defaults(self):
        """Test creating IssueCreate with default empty tuples."""
        issue_create = IssueCreate(
            title="Simple issue",
            body="Body",
        )

        assert issue_create.title == "Simple issue"
        assert issue_create.body == "Body"
        assert issue_create.labels == ()
        assert issue_create.assignees == ()

    def test_labels_and_assignees_are_tuples(self):
        """Test that labels and assignees are tuples."""
        issue_create = IssueCreate(
            title="Test",
            body="Body",
            labels=("label1",),
            assignees=("user1",),
        )

        assert isinstance(issue_create.labels, tuple)
        assert isinstance(issue_create.assignees, tuple)

    def test_frozen_immutable(self):
        """Test that IssueCreate is frozen."""
        issue_create = IssueCreate(title="Test", body="Body")

        with pytest.raises(AttributeError):
            issue_create.title = "Changed"  # type: ignore


class TestIssueMatch:
    """Test IssueMatch dataclass."""

    def test_create_issue_match(self):
        """Test creating an IssueMatch."""
        issue = Issue(
            number=42,
            title="Similar Issue",
            body="Body",
            url="https://example.com/42",
            state=IssueState.OPEN,
            labels=(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="user",
        )

        match = IssueMatch(
            issue=issue,
            confidence=0.92,
            match_reasons=(
                "Same exception type",
                "Similar stack trace",
                "Matching file path",
            ),
        )

        assert match.issue == issue
        assert match.confidence == 0.92
        assert len(match.match_reasons) == 3
        assert "Same exception type" in match.match_reasons

    def test_match_reasons_is_tuple(self):
        """Test that match_reasons is a tuple."""
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

        match = IssueMatch(
            issue=issue,
            confidence=0.8,
            match_reasons=("reason1", "reason2"),
        )

        assert isinstance(match.match_reasons, tuple)

    def test_frozen_immutable(self):
        """Test that IssueMatch is frozen."""
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

        match = IssueMatch(issue=issue, confidence=0.8, match_reasons=())

        with pytest.raises(AttributeError):
            match.confidence = 0.9  # type: ignore
