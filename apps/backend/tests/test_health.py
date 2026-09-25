from fastapi.testclient import TestClient


def test_health_reports_unconfigured_database_without_crashing(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "service": "company-intelligence-api",
        "version": "0.1.0",
        "environment": "test",
        "dependencies": {"database": "not_configured", "storage": "ready", "ocr": "disabled"},
    }
