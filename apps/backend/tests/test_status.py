from fastapi.testclient import TestClient


def test_status_marks_future_components_as_planned(client: TestClient) -> None:
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["application"]["environment"] == "test"
    assert payload["components"]["api"] == "ready"
    assert payload["components"]["database"] == "not_configured"
    assert payload["components"]["credit_engine"] == "unavailable"
    assert payload["components"]["credit_ml"] == "unavailable"
    assert payload["development_stage"]["day"] == 19
    assert payload["components"]["credit_ml_rule_fusion"] == "ready"
    assert payload["components"]["production_credit_fusion"] == "unavailable"
    assert payload["components"]["five_cs"] == "unavailable"
    assert payload["components"]["character_external_research"] == "unavailable"
    assert payload["components"]["automatic_five_cs_refresh"] == "not_implemented"
    assert payload["components"]["collateral_valuation"] == "not_implemented"
    assert payload["components"]["file_upload"] == "unavailable"
    assert payload["core_models"]["audit_log"] == "ready"


def test_cors_allows_configured_frontend(client: TestClient) -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
