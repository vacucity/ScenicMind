from fastapi import HTTPException

from app.main import app, health, latest_prediction


def test_skeleton_contract() -> None:
    assert health() == {"status": "ok"}
    assert "/api/v1/predictions/latest" in app.openapi()["paths"]

    try:
        latest_prediction()
    except HTTPException as error:
        assert error.status_code == 501
    else:
        raise AssertionError("Unconfigured prediction endpoint must return 501")


if __name__ == "__main__":
    test_skeleton_contract()
