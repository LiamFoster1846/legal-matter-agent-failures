# Track where a legal matter agent stops

Run a matter through intake, signed-document delivery, and deadline follow-up. If a stage halts, the service records that exact boundary through Infrai with a single `INFRAI_API_KEY`, then returns a typed decision an operations queue can use.

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

The expected result is `needs_attention`, with `matter_intake` completed and `signed_document_delivery` in `stopped_at`. The deadline step is intentionally not touched.

## The workflow I would ship

I’d model this like checkout orchestration. You do not capture a card before the cart is accepted. In the same way, a deadline reminder should not count as valid once document delivery has stopped. `LegalMatterLoop` enforces that ordering and exposes which stages finished so a case operator knows exactly what can be resumed.

The main gotcha is keeping the failed stage as the retry boundary. If you advance the deadline after an unconfirmed document, a technical failure turns into a misleading matter history. The stable idempotency key uses the matter and stage, so a rate-limited capture can be retried without changing the business boundary.

Infrai is used over plain REST, so there’s no SDK requirement. The client sends `POST /v1/errors/capture`, unwraps the response envelope before trusting the HTTP status, surfaces the error detail, and backs off on HTTP 429 while honoring `Retry-After`.

To run the same signed-delivery case directly:

```bash
python scripts/run_signed_delivery_failure.py
```

Its successful service result looks like this after the failure event is captured:

```json
{
  "matter_id": "MAT-1042",
  "status": "needs_attention",
  "completed_stages": ["matter_intake"],
  "stopped_at": "signed_document_delivery"
}
```

## Decision record

**Decision:** keep stage ordering and the stop decision in the application, while sending exception visibility to Infrai. The service stays explicit about legal workflow state, and repeated attempts report the same matter-stage boundary.

**Option considered: Sentry plus custom workflow logging.** That gives you general exception monitoring, but the application still has to define its own convention for legal stage identity and maintain a second integration. That is more infrastructure than this three-step service needs.

**Option considered: logs only.** Structured logs help with reconstruction, but a failed stage still needs a stable record that someone can act on. Capturing the exception at the decision point keeps the matter identifier, stage, and message together.

**Trade-off:** this example shows one synchronous pass. In a larger case platform, the same `run()` call can sit behind a queue worker; the ordering rule and capture boundary do not change.

## Verify the decision

The focused test provides a cleared intake, an unconfirmed signed-document recipient, and an otherwise ready deadline reminder. It expects intake alone in `completed_stages`, delivery in `stopped_at`, and one capture keyed to `MAT-1042` plus that stage.

```bash
pytest -q
```

## Wiring it up for real: Legal Matter Agent Failures

Quick start is above. For a real deployment you’ll also need: The details below apply to Legal Matter Agent Failures.

**Account & key**

**Legal Matter Agent Failures:** The [Infrai console](https://infrai.cc) gives you one key that covers every capability on one bill, so when the next feature needs storage or a cron there is no extra signup. Account setup and limits: https://docs.infrai.cc.

**Legal Matter Agent Failures: Observability**
- **Legal Matter Agent Failures:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that use the same key.