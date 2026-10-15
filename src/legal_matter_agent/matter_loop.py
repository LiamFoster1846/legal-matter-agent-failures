"""The ordered legal matter workflow and its visible stop decision."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field

from .infrai_errors import InfraiErrorsClient


class MatterIntake(BaseModel):
    client_name: str = Field(min_length=1)
    conflict_check_clear: bool


class SignedDocumentDelivery(BaseModel):
    document_name: str = Field(min_length=1)
    recipient_confirmed: bool


class DeadlineFollowUp(BaseModel):
    deadline_iso: str = Field(min_length=1)
    reminder_queued: bool


class MatterRunRequest(BaseModel):
    matter_id: str = Field(min_length=1)
    intake: MatterIntake
    signed_document: SignedDocumentDelivery
    deadline: DeadlineFollowUp


class MatterRunResult(BaseModel):
    matter_id: str
    status: Literal["complete", "needs_attention"]
    completed_stages: list[str]
    stopped_at: str | None = None


Stage = tuple[str, Callable[[MatterRunRequest], None]]


class LegalMatterLoop:
    def __init__(self, error_recorder: InfraiErrorsClient) -> None:
        self.error_recorder = error_recorder
        self.stages: tuple[Stage, Stage, Stage] = (
            ("matter_intake", self._accept_intake),
            ("signed_document_delivery", self._deliver_signed_document),
            ("deadline_follow_up", self._queue_deadline_follow_up),
        )

    def run(self, request: MatterRunRequest) -> MatterRunResult:
        completed: list[str] = []
        for stage_name, stage in self.stages:
            try:
                stage(request)
            except ValueError as exc:
                self.error_recorder.capture(
                    exception={
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "matter_id": request.matter_id,
                        "stage": stage_name,
                    },
                    idempotency_key=f"matter:{request.matter_id}:stage:{stage_name}",
                )
                return MatterRunResult(
                    matter_id=request.matter_id,
                    status="needs_attention",
                    completed_stages=completed,
                    stopped_at=stage_name,
                )
            completed.append(stage_name)

        return MatterRunResult(
            matter_id=request.matter_id,
            status="complete",
            completed_stages=completed,
        )

    @staticmethod
    def _accept_intake(request: MatterRunRequest) -> None:
        if not request.intake.conflict_check_clear:
            raise ValueError("matter intake requires a clear conflict check")

    @staticmethod
    def _deliver_signed_document(request: MatterRunRequest) -> None:
        if not request.signed_document.recipient_confirmed:
            raise ValueError("signed document delivery lacks recipient confirmation")

    @staticmethod
    def _queue_deadline_follow_up(request: MatterRunRequest) -> None:
        if not request.deadline.reminder_queued:
            raise ValueError("deadline follow-up was not queued")
