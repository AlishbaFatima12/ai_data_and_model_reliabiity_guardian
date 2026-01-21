"""Dashboard-specific data models.

Models for UI state and timeline events:
- TimelineEvent: Incident timeline event representation
- BusinessImpact: Business impact translation
- DashboardState: User session state
"""

from dashboard.models.timeline_event import TimelineEvent, EventGroup

__all__ = [
    "TimelineEvent",
    "EventGroup",
]
