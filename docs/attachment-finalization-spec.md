# Spec: Attachment-aware document finalization (v2 — inverted)

Status: draft for implementation (revises the original consumer-side design)
Scope: **all consumers** — `arqueos_robot` and `gastos_robot` (for now) — plus
`sical-robot` as the assembly orchestrator.

> Location note: this file lives in `arqueos_robot/docs/` for history, but it
> is now a **cross-project** spec (sical-robot + every consumer). Treat it as
> the shared source of truth; copy into `sical-robot/docs/` if that becomes
> the canonical home.

## 0. What changed vs. the original spec

The original design pushed documents **to** the consumer: sical-robot merged
the pooled attachment, uploaded it, and sent `operation_data.attachment` so
the consumer could fetch + merge + print + stage.

**This revision inverts the flow.** The consumer no longer receives any
attachment. It performs the SICAL operation, captures the *contable*
document it generates, and **returns that PDF to sical-robot** in the result
message. sical-robot then does the merge (contable doc + its own pooled
attachments), the print, and the portafirmas staging.

Rationale:

- The consumer is a brittle UI-automation host. This removes everything but
  the SICAL-PDF capture from it (no fetch / merge / print / stage / retry).
- It deletes the hardest problem entirely: no attachment transport **to** the
  consumer (no S3/presigned across machines).
- Assembly lands where the infrastructure already exists in sical-robot:
  the attachments pool, the pdf-lib merge pipeline, storage backends, the
  Task Monitor (ack/audit/retry UI), and the RabbitMQ recovery mechanism.
- Strict-integrity validation already lives in sical-robot on canonical data
  and is unaffected.

## 1. Goal & scope

For a finalized accounting task (arqueo `_FIN`, or the gasto equivalent):

1. Consumer validates + executes the SICAL operation (unchanged).
2. Consumer captures the contable document SICAL produces, to a PDF.
3. Consumer returns that PDF (bytes + metadata) in the result message.
4. sical-robot, on `taskResult`, merges the contable PDF with any pooled
   attachment(s) bound to the task, prints the result, and stages it for
   the future portafirmas sender.

Applies to **arqueo and gasto** consumers. The capture target differs per
consumer (arqueo: *Talón de Cargo*; gasto: its ADO/operation document) but
the **return envelope and the sical-robot side are consumer-agnostic**.

## 2. Message contract

### 2.1 Outbound (sical-robot → consumer)

- **Remove** population of `operation_data.attachment`. Consumers no longer
  fetch anything. `schema_version` stays for negotiation; the field is simply
  not sent (v1/v2 consumers behave identically).

### 2.2 Result (consumer → sical-robot, `sical_results` queue)

Add a `contable_document` block to the existing result message:

```json
{
  "status": "COMPLETED",
  "operation_id": "<task_id>",
  "result": { "...": "..." },
  "contable_document": {
    "filename": "<num_operacion>.pdf",
    "mime_type": "application/pdf",
    "page_count": 2,
    "size_bytes": 41213,
    "sha256": "ab12...",
    "transport": "inline_base64",        // or "storage_ref"
    "data": "<base64>",                   // when transport=inline_base64
    "ref": null,                          // when transport=storage_ref
    "capture_status": "CAPTURED",         // CAPTURED | FAILED
    "capture_error": null
  }
}
```

**Transport:** the contable doc (Talón de Cargo / ADO doc) is 1–2 pages,
tens of KB, so `inline_base64` in the existing result message is the default
— no new infra, topology-agnostic. A size guard (`MAX_INLINE_BYTES`, default
~2 MB) falls back to `storage_ref` (consumer uploads to the shared backend
and returns a ref) only if a doc ever exceeds it. This reverse-transport is
far cheaper than the original forward one because the contable doc is tiny
vs. the ≤7.5 MB attachments.

**Capture failure:** `capture_status:"FAILED"`, `data:null`, `capture_error`
set. The SICAL operation itself is already committed, so `status` stays
`COMPLETED`. sical-robot records "contable doc missing" and offers re-capture
from the Task Monitor (see §5). The consumer never fabricates a document.

### 2.3 Phase 3C consumer-ack — retired

The reserved consumer→producer `result.attachment` ack
(`ATTACHED|FAILED`) is no longer meaningful: sical-robot does the attaching
and knows the outcome locally. The Phase 3C ack path in sical-robot
`main.js` is repurposed to record the **capture** result and the local
**assembly** result instead (see §9 migration).

## 3. Consumer responsibilities (arqueos_robot AND gastos_robot)

Keep only the capture. Concretely, per consumer:

- Validate + execute the SICAL op — unchanged.
- Capture the contable document to a PDF via the SICAL "Guardar PDF" →
  "Guardar como" automation (the `sical_capture` module). Selectors differ
  per consumer/document; the **return envelope is identical**.
- Read the captured PDF bytes, compute sha256/size/page_count, attach as
  `contable_document` (base64) on the result; or upload + ref if over the
  size guard.
- On capture failure: set `capture_status:"FAILED"` + `capture_error`; do
  **not** change the operation status (it is committed).
- **Drop** entirely: `fetcher`, `merger`, `printer`, `stager`, `pipeline`.

Shared contract: a tiny `capture_and_return` helper (capture → envelope) is
common to both robots. The two are separate sibling projects with no shared
package today — decide shared lib vs. vendored copy (was Phase B; still
open). The SICAL UI selectors remain **UNVERIFIED** until a dry-run on the
live SICAL build (no test env available to the user).

## 4. sical-robot responsibilities

On `taskResult` carrying `contable_document` (`capture_status=CAPTURED`):

1. **Decode + verify** — base64-decode (or fetch the ref), verify
   `size_bytes` + `sha256` (strict; a mismatch = assembly failure, do not
   print a corrupt accounting doc).
2. **Persist** the contable PDF as a per-task artifact (reuse the
   attachments storage backend; new artifact kind alongside the merged-PDF
   row, or a dedicated `task_contable_documents` row — see §8).
3. **Merge** — contable PDF **first**, then the pooled attachment(s) bound
   to that task, via the existing pdf-lib merge pipeline
   (`src/services/attachments/merge`). No attachment bound → the contable
   PDF is the final artifact as-is.
4. **Print** — silent print of the final PDF from the sical-robot host
   (operator desktop; better printer/portafirmas access than the robot box).
5. **Stage for portafirmas** — copy final PDF + JSON sidecar into the
   portafirmas outbox (reuse/extend the attachments service).
6. **Recovery** — the post-result assembly (decode→merge→print→stage) must
   be resumable. Extend the existing recovery mechanism: persist an
   assembly state per task (`PENDING → MERGED → PRINTED → STAGED | FAILED`)
   so an app restart between "result arrived" and "staged" re-drives the
   remaining steps; idempotent on sha256.
7. **Task Monitor** — surface assembly/print/portafirmas state. Reuse the
   existing attachment badges (Phase 3C), now driven by **local** state, not
   a consumer ack. Add a "re-assemble / re-print / re-stage" row action and
   a "request re-capture" action when `capture_status=FAILED`.

## 5. Failure policy

The SICAL operation is committed before the doc step, so doc-side failure
never regresses the operation outcome. Specifics:

- **Consumer capture fails** → result has `capture_status:FAILED`. Task
  Monitor flags "contable doc missing"; operator can trigger re-capture
  (re-publish a capture-only request) or accept manual handling. No print /
  stage. Do not fabricate.
- **No attachment bound** → contable-only is the legitimate normal case:
  print + stage the contable PDF as-is. (Replaces the consumer's old
  in-app print — see §7.)
- **Attachment bound but merge fails** → **retry, then surface; never
  silently print contable-only.** Retry the read/assemble step
  `ASSEMBLY_RETRIES` times (default **3**, short backoff, configurable):
  the pdf-lib merge itself is deterministic, but the retry covers transient
  I/O (reading the contable PDF / pooled docs from storage). If it still
  fails, mark the task FAILED-assembly in Task Monitor and let the operator
  decide (retry / proceed contable-only / fix source). Silently dropping
  required documentation violates the strict-integrity preference.
- **Print or stage fails** → same retry-then-surface; assembly state stays
  recoverable. Operation already done.

## 6. Backward compatibility / printing locus

Today the consumer prints the contable doc in-app. Under this design
sical-robot is the printer for **every finalized task** (it must hold the
PDF to merge/stage).

**Decided:** option (a) — sical-robot prints all finalized tasks (uniform;
consumer never prints), enabling portafirmas for all via a single print
path. Gated by a rollout feature flag whose **default is OFF**: until the
capture+assembly path is verified on the live SICAL build, the consumer
keeps its current in-app print and sical-robot does **not** assemble/print.
Flip the flag ON per environment once verified.

## 7. Transport / config

sical-robot (move config here; reuse `app-settings.json` + attachments
service):

- `MAX_INLINE_BYTES` (default ~2 MB) — inline vs. storage_ref threshold.
- Portafirmas staging dir, printer name, print tool — now sical-robot side.
- Storage backend already configured for attachments; reused for the
  contable artifact and (rare) reverse upload.

Consumers (`config.py`): keep only a capture work dir
(`SICAL_PDF_WORKDIR`). **Remove** `PORTAFIRMAS_STAGING_DIR`,
`PDF_PRINTER_NAME`, `SUMATRA_PATH`, `ATTACHMENT_FETCH_*`. `requirements.txt`:
drop `requests`; `pypdf` optional (only for page_count) — may drop.

## 8. Data model (sical-robot)

**Decided:** dedicated table + explicit assembly state (clean separation,
no semantic overload of the Phase 3C ack columns):

- New table `task_contable_documents` — the contable PDF returned by the
  consumer per task (filename, mime, page_count, size_bytes, sha256,
  storage_key, capture_status, capture_error, received_at). Idempotent on
  sha256.
- `task_merged_documents` keeps the **final** merged artifact (unchanged).
- **Implemented deviation:** `assembly_status` lives on
  `task_contable_documents` (RECEIVED → MERGED → PRINTED → STAGED | FAILED),
  not on `task_merged_documents`. Rationale: the lifecycle starts at
  contable receipt — before any merged row exists — so the always-present,
  first-created row is the correct single source of truth. The merged-doc
  row is created later by the existing `upsertMergedDocument` and linked via
  `task_contable_documents.merged_document_id`.
- `liquidation_files` / pool / assignment tables unchanged.

## 9. Migration — delta vs. the already-merged Phase A

Phase A (consumer-side) was implemented in `arqueos_robot`. Under v2:

**Remove (arqueos_robot):**
- `doc_pipeline/fetcher.py`, `merger.py`, `printer.py`, `stager.py`,
  `pipeline.py` and their tests (`tests/test_doc_pipeline.py` largely;
  keep only any capture tests).
- `config.py`: the fetch/print/stage settings listed in §7.
- `requirements.txt`: `requests` (and maybe `pypdf`).

**Keep / adapt (arqueos_robot):**
- `doc_pipeline/sical_capture.py` — the only surviving piece (still
  UNVERIFIED). Wrapped by a new `capture_and_return` returning the envelope.
- `arqueo_tasks.py`: replace `finalize_with_attachment` with
  capture-and-return; `OperationResult.attachment_*` → `capture_status` /
  `capture_error` (+ the PDF payload carried out-of-band on the result, not
  in the dataclass dump if large).
- `arqueo_task_consumer.py`: stop reading `operation_data.attachment`;
  attach `contable_document` to the result.
- `status_manager.py` / `arqueos_gui.py` / `task_history_db.py`: the rich
  attachment/portafirmas surfacing collapses to a simple
  "contable captured / returned / failed" indicator; the merge/print/
  portafirmas/ack surfacing **moves to sical-robot's Task Monitor**.

**Add (sical-robot):**
- `taskResult` handler: decode/verify/persist contable doc; drive
  merge → print → stage; assembly-state recovery; Task Monitor surface +
  re-assemble / re-capture actions.
- Stop populating outbound `operation_data.attachment`; repurpose the
  Phase 3C ack path to capture/assembly state.

**Add (gastos_robot) — Phase B':**
- Mirror the arqueo consumer: `sical_capture` for the gasto document +
  `capture_and_return`. sical-robot side is consumer-agnostic, so little
  extra there.

## 10. Decisions (locked)

1. **Printing locus** — sical-robot prints **all** finalized tasks
   (uniform; consumer never prints), behind a rollout flag.
2. **Rollout flag default = OFF** — consumer keeps in-app print and
   sical-robot does not assemble/print until the flag is flipped per
   environment after a live-SICAL verification.
3. **Attachment-bound merge failure** — retry then surface; never silently
   print contable-only.
4. **Assembly retries** — `ASSEMBLY_RETRIES` default **3**, short backoff,
   configurable (covers transient storage I/O; merge itself is
   deterministic).
5. **Return transport** — `inline_base64` by default;
   `MAX_INLINE_BYTES` default **~2 MB** → `storage_ref` fallback above it.
6. **Shared consumer module** — **vendored copy** of the capture+envelope
   module in each robot (sync changes by hand; accept drift risk).
7. **Data model** — dedicated `task_contable_documents` table + explicit
   `assembly_status` column on `task_merged_documents` (no ack-column
   repurposing).
8. **Gasto capture** — same pattern as arqueo (the ADO document via
   "Guardar PDF" → "Guardar como"); selectors **UNVERIFIED** until dry-run.

### Still pending (verification, not decisions)

- **SICAL capture selectors** for both consumers — require a live dry-run
  on the current SICAL build; no test environment available. Until then
  every selector stays `# UNVERIFIED` and the rollout flag stays OFF.
- **Assembly-state recovery design** — implementation detail (no user
  decision): persist `assembly_status` per task and hook the existing
  `TaskQueueManager.runRecovery` (Phase 1/2) so that, on restart, tasks in
  `PENDING/MERGED/PRINTED` re-drive the remaining decode→merge→print→stage
  steps idempotently (keyed on the contable sha256).

## 11. Phasing

- **Phase A′ (arqueo)** — strip Phase A consumer modules to capture-only;
  `arqueo_task_consumer` returns `contable_document`; sical-robot taskResult
  assembly + print + portafirmas + recovery + Task Monitor.
- **Phase B′ (gasto)** — `gastos_robot` capture-and-return for the ADO
  document (same Guardar-PDF pattern as arqueo, selectors UNVERIFIED) via a
  **vendored copy** of the capture module; sical-robot path already
  consumer-agnostic.
- Rollout behind a feature flag, **default OFF**: consumer in-app print
  stays until the capture+assembly path is verified on the live SICAL
  build, then flip ON per environment.
