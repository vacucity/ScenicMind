from fastapi import HTTPException

from app.main import app, health
from app.modules.module_one import module_one_output
from app.modules.module_two import module_two_output


def test_skeleton_contract() -> None:
    assert health() == {"status": "ok"}
    paths = app.openapi()["paths"]
    assert "/api/v1/module-one/output" in paths
    assert "/api/v1/module-two/output" in paths

    for output in (module_one_output, module_two_output):
        try:
            output()
        except HTTPException as error:
            assert error.status_code == 501
        else:
            raise AssertionError("Unconfigured module must return 501")


if __name__ == "__main__":
    test_skeleton_contract()
