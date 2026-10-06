from uuid import UUID, uuid4

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db
from app.main import create_app
from app.models.company import Company
from app.models.runtime import CompanyAccess
from app.models.user import User
from app.runtime.security import PASSWORDS, authorize_request, get_security_db, issue_token

pytestmark = pytest.mark.strict_auth


@pytest.fixture
def secure_app(database_engine, tmp_path):
    with database_engine.connect() as connection:
        transaction = connection.begin()
        config = Settings(
            _env_file=None,
            app_env="test",
            database_url="postgresql://unused",
            auth_signing_key=SecretStr("test-key-" * 8),
            local_storage_path=tmp_path,
            login_rate_limit_per_minute=3,
        )
        with Session(connection, join_transaction_mode="create_savepoint") as setup:
            first, second = (
                Company(legal_name="Allowed Company"),
                Company(legal_name="Other Company"),
            )
            user = User(
                email=f"auth-{uuid4()}@example.test",
                reviewer_role="VIEWER",
                password_hash=PASSWORDS.hash("a-test-password"),
            )
            setup.add_all([first, second, user])
            setup.flush()
            setup.add(CompanyAccess(user_id=user.id, company_id=first.id))
            setup.commit()
            user_id, email, first_id, second_id = user.id, user.email, first.id, second.id
            token = issue_token(user, config)
        app = create_app(config)

        def auth_session():
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                yield session

        def endpoint_session(request: Request):
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                principal = getattr(request.state, "principal", None)
                if principal and principal.role != "ADMIN":
                    session.info.update(
                        company_scope=list(principal.companies), user_scope=principal.user_id
                    )
                yield session

        app.dependency_overrides[get_security_db] = auth_session
        app.dependency_overrides[get_db] = endpoint_session

        @app.get(
            "/api/v1/companies/{company_id}/access-probe", dependencies=[Depends(authorize_request)]
        )
        def access_probe(company_id: UUID):
            return {"company_id": str(company_id)}

        with TestClient(app) as client:
            yield client, config, connection, user_id, email, first_id, second_id, token
        transaction.rollback()


def test_login_identity_and_disabled_account_revocation(secure_app):
    client, _, connection, user_id, email, first_id, _, token = secure_app
    response = client.post(
        "/api/v1/auth/token", json={"email": email, "password": "a-test-password"}
    )
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["company_ids"] == [str(first_id)]
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        session.get(User, user_id).account_status = "DISABLED"
        session.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_role_company_and_actor_boundaries(secure_app):
    client, _, _, _, _, allowed, denied, token = secure_app
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/admin/runtime", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/jobs",
            headers=headers,
            json={
                "job_type": "REPORT_360",
                "company_id": str(allowed),
                "idempotency_key": "role-denied",
            },
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/company-intelligence-reports",
            headers=headers,
            params={"company": str(denied), "actor_user_id": token_subject(token)},
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/status", headers=headers, params={"actor_user_id": str(uuid4())}
        ).status_code
        == 403
    )


def token_subject(token):
    import jwt

    return jwt.decode(token, options={"verify_signature": False})["sub"]


def test_bad_password_and_login_rate_limit(secure_app):
    client, _, _, _, email, *_ = secure_app
    for _ in range(3):
        response = client.post("/api/v1/auth/token", json={"email": email, "password": "wrong"})
        assert response.status_code == 401
        assert "wrong" not in response.text
    response = client.post("/api/v1/auth/token", json={"email": email, "password": "wrong"})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


def test_body_cannot_mask_an_unauthorized_path_reference(secure_app):
    client, _, _, _, _, allowed, denied, token = secure_app
    response = client.request(
        "GET",
        f"/api/v1/companies/{denied}/access-probe",
        headers={"Authorization": f"Bearer {token}"},
        json={"company_id": str(allowed)},
    )
    assert response.status_code == 403
