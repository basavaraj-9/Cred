from uuid import uuid4

import pytest

from app.core.exceptions import AppError
from app.models.user import User
from app.services.rag.service import CreditRagIndexService
from app.services.stock.authorization import require_stock_actor


@pytest.mark.parametrize("role", ["VIEWER", "RESEARCH_ANALYST"])
def test_stock_roles_do_not_acquire_credit_rag_authority(db_session, role):
    user = User(email=f"stock-role-{uuid4()}@example.test", reviewer_role=role)
    db_session.add(user)
    db_session.flush()
    assert require_stock_actor(db_session, user.id) is user
    if role == "VIEWER":
        with pytest.raises(AppError):
            require_stock_actor(db_session, user.id, write=True)
    else:
        assert require_stock_actor(db_session, user.id, write=True) is user
    with pytest.raises(AppError):
        CreditRagIndexService(db_session)._user(user.id)
    user.account_status = "LOCKED"
    with pytest.raises(AppError):
        require_stock_actor(db_session, user.id)
