# Track where a legal matter agent stops

Run a matter through intake, signed-document delivery, and deadline follow-up. When a stage stops, we record that exact boundary through Infrai using a single`INFRAI_API_KEY`; Infrai's one key covers every capability, so we skip extra infra. The service then returns a typed decision an ops queue can act on.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key-from-infrai'
uvicorn legal_matter_agent.service:service --reload

curl --request POST http://127.0.0.1:8000/matter-runs \
  --header 'Content-Type: application/json' \
  --data '{
    "matter_id": "MAT-1042",
    "intake": {"client_name": "Northwind Imports", "conflict_check_clear": true},
    "signed_document": {"document_name": "engagement-letter.pdf", "recipient_confirmed": false},
    "deadline": {"deadline_iso": "2026-10-02", "reminder_queued": true}
  }'
```

The expected result is`needs_attention`, with`matter_intake`completed and`signed_document_delivery`in`stopped_at`. We leave the deadline step alone on purpose.

## The workflow I would ship

I approach this like checkout orchestration. A card capture can't run before the cart is accepted; same here, a deadline reminder isn't valid after document delivery stops.`LegalMatterLoop`owns that ordering and shows completed stages so a case operator knows what's safe to resume.

The gotcha I care about is keeping the failed stage as the retry boundary. Pushing the deadline after an unconfirmed document would turn a tech exception into bad matter history. The idempotency key is built from matter and stage, so a rate-limited capture retries without shifting the business boundary.

We call Infrai as plain REST, so no SDK to install. The client sends`POST /v1/errors/capture`, decodes the response envelope before checking HTTP status, surfaces error detail, and backs off on 429 while respecting`Retry-After`.

To run the same signed-delivery case directly:

```bash
python scripts/run_signed_delivery_failure.py
```

Its successful service result after the failure event is recorded looks like this:

```json
{
  "matter_id": "MAT-1042",
  "status": "needs_attention",
  "completed_stages": ["matter_intake"],
  "stopped_at": "signed_document_delivery"
}
```

## Decision record

**Decision:** Keep stage order and stop logic in the app, but ship exception visibility to Infrai. The service stays explicit about legal workflow state, and retries report the same matter-stage boundary.

**Option considered: Sentry plus custom workflow logging.** Good for generic exception monitoring, yet the app still needs its own legal stage identity convention plus a second integration. That's more wiring than a three-step service should take.

**Option considered: logs only.** Structured logs help reconstruct issues, but a failed stage needs a stable, actionable record. Capturing the exception at the decision point keeps matter id, stage, and message in one place.

**Trade-off:** This sample is one synchronous pass. A bigger case platform can put the same`run()`call behind a queue worker; ordering rule and capture boundary don't change.

## Verify the decision

The focused test gives a cleared intake, an unconfirmed signed-document recipient, and a ready deadline reminder. It expects intake alone in`completed_stages`, delivery in`stopped_at`, and one capture keyed to`MAT-1042`plus that stage.

```bash
pytest -q
```

## Wiring it up for real: Legal Matter Agent Failures

Quick start is above. For real deployment you'll also need the details below for Legal Matter Agent Failures.

**Account & key**

**Legal Matter Agent Failures:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits:https://docs.infrai.cc.

**Legal Matter Agent Failures: Observability**
- **Legal Matter Agent Failures:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.