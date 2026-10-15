"""Run the concrete signed-delivery stop case without starting HTTP."""

import json

from legal_matter_agent.infrai_errors import InfraiErrorsClient
from legal_matter_agent.matter_loop import LegalMatterLoop, MatterRunRequest


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

result = LegalMatterLoop(InfraiErrorsClient()).run(request)
print(json.dumps(result.model_dump(), indent=2))
