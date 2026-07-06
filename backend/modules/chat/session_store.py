"""In-memory session state for the Phase 1 button flow (see #17).

Lives only for the backend process's lifetime -- no persistence, no TTL/expiry.
That's an intentional scope cut for the walking skeleton, not an oversight.
"""

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class SessionState:
    session_id: str
    step: str = "greeting"
    selected_domains: list[str] = field(default_factory=list)


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
