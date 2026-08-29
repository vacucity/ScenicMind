from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from ..contracts import ModuleOutput
from ..module_two_contracts import ReportRequest, spot_id_for
from ..module_two_service import build_report, list_spots

router = APIRouter(prefix="/api/v1/module-two", tags=["模块二"])


def get_output(spot: str = "九寨沟") -> ModuleOutput:
    report = build_report(ReportRequest(spot_id=spot_id_for(spot), spot_name=spot))
    return ModuleOutput(
        generated_at=datetime.now(UTC),
        data=report.model_dump(mode="json", by_alias=True),
        text=report.executive_summary,
    )


@router.get("/output", response_model=ModuleOutput, response_model_by_alias=True)
def module_two_output(
    spot: Annotated[str, Query(min_length=1, max_length=80)] = "九寨沟",
) -> ModuleOutput:
    return get_output(spot)


@router.post("/reports", response_model=ModuleOutput, response_model_by_alias=True)
def generate_report(request: ReportRequest) -> ModuleOutput:
    report = build_report(request)
    return ModuleOutput(
        generated_at=datetime.now(UTC),
        data=report.model_dump(mode="json", by_alias=True),
        text=report.executive_summary,
    )


@router.get("/spots")
def module_two_spots() -> dict[str, list[str]]:
    return {"spots": list_spots()}
