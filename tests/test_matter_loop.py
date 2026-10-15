from legal_matter_agent.matter_loop import LegalMatterLoop, MatterRunRequest


class RecordingErrors:
    def __init__(self) -> None:
        self.captures: list[dict[str, object]] = []

    def capture(self, *, exception: dict[str, object], idempotency_key: str) -> dict[str, object]:
        self.captures.append(
            {"exception": exception, "idempotency_key": idempotency_key}
        )
        return {"event_id": "evt-test"}


def test_signed_delivery_failure_stops_before_deadline_follow_up() -> None:
    errors = RecordingErrors()
    request = MatterRunRequest.model_validate(
        {
            "matter_id": "MAT-1042",
            "intake": {"client_name": "Northwind Imports", "conflict_check_clear": True},
            "signed_document": {
                "document_name": "engagement-letter.pdf",
                "recipient_confirmed": False,
            },
            "deadline": {"deadline_iso": "2026-10-02", "reminder_queued": True},
        }
    )

    result = LegalMatterLoop(errors).run(request)

    assert result.model_dump() == {
        "matter_id": "MAT-1042",
        "status": "needs_attention",
        "completed_stages": ["matter_intake"],
        "stopped_at": "signed_document_delivery",
    }
    assert errors.captures == [
        {
            "exception": {
                "type": "ValueError",
                "message": "signed document delivery lacks recipient confirmation",
                "matter_id": "MAT-1042",
                "stage": "signed_document_delivery",
            },
            "idempotency_key": "matter:MAT-1042:stage:signed_document_delivery",
        }
    ]
