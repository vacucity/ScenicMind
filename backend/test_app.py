from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routers import analyses


def sample_csv(days: int = 70) -> bytes:
    rows = ["date,visitors,weather_temp_mean_lag1,known_reserved_count,daily_capacity"]
    for index in range(days):
        date = __import__("datetime").date(2026, 5, 1) + __import__("datetime").timedelta(days=index)
        visitors = 2400 + index * 17 + (650 if date.weekday() >= 5 else 0)
        temperature = 18 + (index % 12) * 0.7
        rows.append(f"{date.isoformat()},{visitors},{temperature:.1f},{500 + index * 3},12000")
    return ("\n".join(rows) + "\n").encode("utf-8")


def test_full_product_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.sqlite3")
    monkeypatch.setattr(analyses, "UPLOAD_DIR", tmp_path / "uploads")

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

        registration = client.post(
            "/api/v1/auth/register",
            json={"username": "tester", "email": "tester@example.com", "password": "TestPass123!"},
        )
        assert registration.status_code == 201

        login = client.post(
            "/api/v1/auth/login",
            json={"username": "tester", "password": "TestPass123!"},
        )
        assert login.status_code == 200
        token = login.json()["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}

        upload = client.post(
            "/api/v1/analyses",
            headers=headers,
            files={"file": ("daily_visitors.csv", BytesIO(sample_csv()), "text/csv")},
        )
        assert upload.status_code == 201, upload.text
        payload = upload.json()
        result = payload["result"]
        assert payload["status"] == "completed"
        assert result["latestActual"]["date"] == "2026-07-09"
        assert result["latestActual"]["visitors"] == 3573
        assert len(result["forecastPoints"]) == 30
        assert set(result["horizons"]) == {"7", "14", "30"}
        assert result["dataAvailability"]["weather"]["status"] == "uploaded"
        assert result["dataAvailability"]["reservation"]["status"] == "uploaded"
        assert result["dataAvailability"]["capacity"]["status"] == "uploaded"
        assert "feature_importance" not in result

        latest = client.get("/api/v1/analyses/latest", headers=headers)
        assert latest.status_code == 200
        assert latest.json()["analysisId"] == payload["analysisId"]

        importance = client.get(f"/api/v1/analyses/{payload['analysisId']}/importance", headers=headers)
        assert importance.status_code == 200
        assert "feature_importance" in importance.json()
        semantic_groups = importance.json()["semantic_groups"]
        assert semantic_groups
        assert semantic_groups[0]["label"] == "历史客流走势"
        assert round(sum(group["importance"] for group in semantic_groups)) == 100

        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_rejects_short_dataset(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "short.sqlite3")
    monkeypatch.setattr(analyses, "UPLOAD_DIR", tmp_path / "uploads-short")
    with TestClient(app) as client:
        registration = client.post(
            "/api/v1/auth/register",
            json={"username": "short", "email": "short@example.com", "password": "TestPass123!"},
        )
        token = registration.json()["accessToken"]
        response = client.post(
            "/api/v1/analyses",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("short.csv", BytesIO(sample_csv(14)), "text/csv")},
        )
        assert response.status_code == 422
        assert "至少需要 21 天" in response.json()["detail"]
