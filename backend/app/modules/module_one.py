from fastapi import APIRouter, HTTPException

from ..contracts import ModuleOutput

router = APIRouter(prefix="/api/v1/module-one", tags=["模块一"])


def get_output() -> ModuleOutput:
    """Replace this function body with the module-one implementation."""

    raise NotImplementedError("Module one is not connected")


@router.get("/output", response_model=ModuleOutput, response_model_by_alias=True)
def module_one_output() -> ModuleOutput:
    try:
        return get_output()
    except NotImplementedError as error:
        raise HTTPException(status_code=501, detail=str(error)) from error
