"""Named exceptions for the Alfred task operating system."""

from __future__ import annotations


class TaskSystemError(Exception):
    """Base class for task-system errors."""


class TaskValidationError(TaskSystemError):
    """Raised when task-system input fails validation."""


class TaskAuthorizationError(TaskSystemError):
    """Raised when a user attempts to access or mutate another user's task data."""


class TaskBoardNotFoundError(TaskSystemError):
    """Raised when a board or column cannot be found for a user."""


class TaskColumnInvariantError(TaskSystemError):
    """Raised when a board's standard column invariant cannot be repaired."""


class TaskNotFoundError(TaskSystemError):
    """Raised when a task cannot be found for a user."""


class TaskProjectNotFoundError(TaskSystemError):
    """Raised when a task project cannot be found for a user."""


class TaskCalendarEventNotFoundError(TaskSystemError):
    """Raised when a calendar event cannot be found for a user."""


class TaskFocusSessionNotFoundError(TaskSystemError):
    """Raised when a focus session cannot be found for a user."""


class TaskRewardNotFoundError(TaskSystemError):
    """Raised when a reward definition or earned reward cannot be found for a user."""


class TaskPlanningUnavailableError(TaskSystemError):
    """Raised when the task planner model is unavailable."""


class TaskPlanningParseError(TaskSystemError):
    """Raised when the task planner returns malformed output."""


class TaskMigrationConflictError(TaskSystemError):
    """Raised when legacy Today todo migration finds a conflict."""


class RewardComputationError(TaskSystemError):
    """Raised when reward calculation fails."""


class InvalidTimezoneError(TaskSystemError):
    """Raised when a timezone name is invalid."""


class TaskScheduleConflictError(TaskSystemError):
    """Raised when a focus/calendar block conflicts with another block."""


__all__ = [
    "InvalidTimezoneError",
    "RewardComputationError",
    "TaskAuthorizationError",
    "TaskBoardNotFoundError",
    "TaskCalendarEventNotFoundError",
    "TaskColumnInvariantError",
    "TaskFocusSessionNotFoundError",
    "TaskMigrationConflictError",
    "TaskNotFoundError",
    "TaskProjectNotFoundError",
    "TaskPlanningParseError",
    "TaskPlanningUnavailableError",
    "TaskRewardNotFoundError",
    "TaskScheduleConflictError",
    "TaskSystemError",
    "TaskValidationError",
]
