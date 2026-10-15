"""FastAPI entry point for running one legal matter agent pass."""

from fastapi import Depends, FastAPI, HTTPException

from .infrai_errors import InfraiError, InfraiErrorsClient
from .matter_loop import LegalMatterLoop, MatterRunRequest, MatterRunResult

service = FastAPI(title="Legal matter agent failure tracker")


def build_loop() -> LegalMatterLoop:
    return LegalMatterLoop(InfraiErrorsClient())


@service.post("/matter-runs", response_model=MatterRunResult)
def run_matter(
    request: MatterRunRequest,
    loop: LegalMatterLoop = Depends(build_loop),
) -> MatterRunResult:
    try:
        return loop.run(request)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "error": exc.detail},
        ) from exc
