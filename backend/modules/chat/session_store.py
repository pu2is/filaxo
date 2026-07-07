"""In-memory session state for the Phase 1 button flow (see #17).

Lives only for the backend process's lifetime -- no persistence, no TTL/expiry.
That's an intentional scope cut for the walking skeleton, not an oversight.
"""

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class SessionState:
    session_id: str
    # Funnel position: "greeting" | "scope" | "time" | "ready" (state machine in service.py,
    # #22/#25/#31).
    step: str = "greeting"
    # Scope-tree path walked so far, e.g. ["LEAD"] right after select_domain, then
    # ["LEAD", "SCORING"] once a leaf is reached (#31, D5 tree drilling). Empty at
    # "greeting". Cross-thema combination is still MVP 2 -- this path only ever has one
    # thema as its root, never more than one tree walked at a time.
    scope_path: list[str] = field(default_factory=list)
    # Time-range key (one of service.TIME_RANGE_LABELS), set at the "time" step. Stays
    # None if the leaf reached has no date facet (#31 skips the time step entirely then)
    # or before the step is reached at all.
    time_range: str | None = None


sessions: dict[str, SessionState] = {}


def get_or_create(session_id: str | None) -> SessionState:
    """Look up an existing session, or start one -- keyed by the caller's id when given.

    Only mints a fresh uuid when `session_id` is None. A non-None id that isn't in the
    store yet (e.g. the client already generated one) is honored as the new session's key
    instead of being replaced, so the caller's id and the stored session never diverge.
    """
    if session_id is not None and session_id in sessions:
        return sessions[session_id]

    resolved_id = session_id or str(uuid4())
    state = SessionState(session_id=resolved_id)
    sessions[resolved_id] = state
    return state
