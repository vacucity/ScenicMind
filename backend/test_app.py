from datetime import date

from app.main import app, health
from app.module_two_contracts import FeatureDriver, ForecastPoint, ReportRequest
from app.modules.module_one import module_one_output
from app.modules.module_two import generate_report, module_two_output, module_two_spots


def test_application_contracts() -> None:
    assert health() == {"status": "ok"}
    paths = app.openapi()["paths"]
    assert "/api/v1/module-one/output" in paths
    assert "/api/v1/module-two/output" in paths
    assert "/api/v1/module-two/reports" in paths
    assert "/api/v1/module-two/spots" in paths


def test_module_one_demo_forecast() -> None:
    data = module_one_output().data
    assert data["spotName"] == "黄果树瀑布"
    assert data["today"]["predicted"] > 0
    assert len(data["history"]) == 30
    assert len(data["forecast"]) == 7
    assert len(data["week"]) == 7
    assert data["demo"] is True


def test_module_two_demo_report_is_evidence_bound() -> None:
    output = module_two_output()
    report = output.data
    assert report["spotName"] == "黄果树瀑布"
    assert len(report["forecast"]) == 7
    assert len(report["drivers"]) >= 3
    assert len(report["recommendations"]) >= 3
    assert report["visitorInsight"]["commentCount"] > 0

    evidence_ids = {
        item["evidenceId"] for item in report["visitorInsight"]["evidence"]
    }
    for recommendation in report["recommendations"]:
        assert set(recommendation["evidenceRefs"]).issubset(evidence_ids)


def test_module_two_accepts_module_one_payload() -> None:
    request = ReportRequest(
        spot_id="test-spot",
        spot_name="测试景区",
        capacity=10_000,
        model_version="unit-test-model",
        data_snapshot="snapshot-001",
        forecast=[
            ForecastPoint(
                date=date(2026, 9, 1),
                predicted_visitors=8_500,
                p90_visitors=9_300,
                capacity=10_000,
            )
        ],
        drivers=[
            FeatureDriver(
                feature="reservation_velocity",
                label="预约增速",
                contribution_visitors=1_200,
                direction="positive",
                explanation="测试驱动因素",
            )
        ],
    )
    report = generate_report(request).data
    assert report["kpis"]["forecastTotal"] == 8_500
    assert report["kpis"]["peakCapacityRate"] == 0.85
    assert report["trace"]["modelVersion"] == "unit-test-model"
    assert report["trace"]["dataSnapshot"] == "snapshot-001"


def test_module_two_spot_catalog() -> None:
    spots = module_two_spots()["spots"]
    assert "黄果树瀑布" in spots
    assert "贵州全域/综合" in spots


if __name__ == "__main__":
    test_application_contracts()
    test_module_two_demo_report_is_evidence_bound()
    test_module_two_accepts_module_one_payload()
    test_module_two_spot_catalog()
