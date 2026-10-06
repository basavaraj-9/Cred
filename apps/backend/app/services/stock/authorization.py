"""Stock actor checks, independent of credit retrieval authority.

Legacy service actors remain supported; the HTTP runtime policy additionally
restricts stock writes to research analysts and administrators.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.user import User

_BUILD_ROLES = frozenset(
    {
        "ADMIN",
        "RESEARCH_ANALYST",
        "CREDIT_ANALYST",
        "SENIOR_CREDIT_REVIEWER",
        "CREDIT_MANAGER",
        "CREDIT_COMMITTEE_MEMBER",
    }
)


def require_stock_actor(session: Session, user_id: UUID, *, write: bool = False) -> User:
    user = session.get(User, user_id)
    roles = _BUILD_ROLES if write else _BUILD_ROLES | {"VIEWER"}
    if (
        user is None
        or not user.is_active
        or user.account_status != "ACTIVE"
        or user.reviewer_role not in roles
    ):
        raise AppError(
            "STOCK_ACTOR_NOT_AUTHORIZED", "Actor is not authorized for this stock action", 403
        )
    return user
