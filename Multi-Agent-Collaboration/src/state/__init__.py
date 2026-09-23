"""Discussion state package.

Provides centralized discussion state representation, lifecycle tracking,
and extension hooks for persistence and opinion dynamics.
"""

from src.state.discussion_state import DiscussionState, DiscussionStatus

__all__ = ["DiscussionState", "DiscussionStatus"]
