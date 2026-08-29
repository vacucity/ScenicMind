from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from ..contracts import ModuleOutput
from ..module_one_service import build_forecast

router = APIRouter(prefix="/api/v1/module-one", tags=["模块一"])


def get_output(spot: str = "黄果树瀑布") -> ModuleOutput:
    """返回选定景点的客流预测数据（当前为演示口径）。"""
    data = build_forecast(spot_id="huangguoshu", spot_name=spot)
    peak = max(data.forecast, key=lambda item: item.predicted)
    return ModuleOutput(
        generated_at=datetime.now(UTC),
        data=data.model_dump(mode="json", by_alias=True),
        text=(
            f"{spot}客流预测：未来 7 天峰值 {peak.predicted:,} 人，"
            f"出现在 {peak.date:%m月%d日}（演示预测，模块一模型接入后即时更新）。"
        ),
    )


@router.get("/output", response_model=ModuleOutput, response_model_by_alias=True)
def module_one_output(
    spot: Annotated[str, Query(min_length=1, max_length=80)] = "黄果树瀑布",
) -> ModuleOutput:
    return get_output(spot)