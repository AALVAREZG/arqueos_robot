# Session handoff — Contable-assembly feature (Phase A′) + ancillary work

Self-contained context for a follow-up session. Drop this in as the new
session's first read; it replaces the full chat history.

Repo root: `C:\Users\antonioalvarez\desarrollo\python\ayto\automatiza\v10_rabbit\`
Three sibling projects:

- `sical-robot/`     Electron producer (the app the operator drives).
- `arqueos_robot/`   Python arqueo consumer (RPA on a SICAL terminal).
- `gastos_robot/`    Python gasto consumer (untouched this round).

Key spec docs in `arqueos_robot/docs/`:

- `attachment-finalization-spec.md` — the architecture spec (v2 inverted).
- `contable-assembly-dry-run.md`     — operator runbook for first live run.
- `session-handoff.md`               — this file.

---

## 1. Goal

When the consumer finalizes an arqueo (`_FIN`), the SICAL contable doc
(Talón de Cargo) is captured to PDF and returned to sical-robot.
sical-robot merges it with the task's pooled attachment(s), prints it,
and stages it for the future portafirmas sender. Strict integrity is
preserved (no silent fallback when an attachment was expected).

## 2. Architecture (v2 inverted — current)

```
arqueos_robot                              sical-robot
─────────────                              ───────────
validate SICAL op (committed)
capture contable PDF  ──┐
                        │  result message
                        │  {..., contable_document: {base64,sha,size,pages,
                        │   transport:"inline_base64", capture_status}}
                        ▼
                   sical_results queue ───► taskResult handler
                                            (flag-gated)
                                                │
                          decode + verify (strict sha/size)
                                                │
                          persist contable      │  storage/<key>
                          + task_contable_documents row
                                                │
                          merge: [contable, ...pool attachments]
                          (existing attachments engine)
                                                │
                          silent print (Electron, UNVERIFIED)
                                                │
                          stage to portafirmas outbox + sidecar
                                                │
                          assembly_status: RECEIVED→MERGED→PRINTED→STAGED
```

Earlier design (v1) had the consumer doing fetch/merge/print/stage. v2
inverts that to centralize all assembly in sical-robot (better infra
there). v1 code was removed; only `sical_capture.py` survives in the
consumer.

## 3. Implementation status — what shipped this session

### Consumer (`arqueos_robot/`)

- **`doc_pipeline/`** — stripped to capture-only:
  - `sical_capture.py` — UNVERIFIED; SICAL "Guardar PDF" → "Guardar como" UI.
  - `capture_and_return.py` — builds the `contable_document` envelope:
    base64 + sha256/size/page_count; `MAX_INLINE_BYTES` guard
    (`storage_ref` fallback not implemented on the consumer side); never
    raises (capture failure is in the envelope).
- **`arqueo_tasks.py`**:
  - `finalize_capture()` replaces the old `finalize_with_attachment`.
  - `OperationResult`: `capture_status` / `capture_error` (the base64
    payload travels out-of-band as `result._contable_document` so it
    doesn't bloat `dataclasses.asdict`).
  - Gate: `_contable_capture_enabled()` reads `CONTABLE_CAPTURE_ENABLED`
    from `config.py`. **Default now `true`** (activated).
- **`arqueo_task_consumer.py`**:
  - No longer reads `operation_data.attachment`.
  - Attaches `contable_document` to the result message.
  - Per-task `capture_info` forwarded to GUI on completion.
- **`config.py`** — pruned: only `CONTABLE_CAPTURE_ENABLED`,
  `SICAL_PDF_WORKDIR`, `MAX_INLINE_BYTES` (+ existing RabbitMQ keys).
- **`requirements.txt`** — dropped `requests`; kept `pypdf` (optional, for
  page_count).
- **`status_manager.py` / `arqueos_gui.py` / `task_history_db.py`**:
  the old Attachment surface was repurposed to a Contable surface
  (`Contable:` row in Current Task panel, `Doc` column in History
  ✅/⚠️/📄, details modal CONTABLE DOCUMENT section). DB column kept the
  name `attachment_info` internally but stores the capture-info JSON.
- **`logging_setup.py`** (NEW) — central, phase-oriented logging:
  per-task correlation, ASCII-safe formatter, third-party libs pinned to
  WARNING, single console + GUI handler. Phases:
  `RECEIVED / PARSED / DUP-CHECK / SICAL-OPEN / FILL / VALIDATE /
  CONTABLE / RESULT / DONE / FAILED / CONN`. Verbose internals at
  `ARQUEOS_LOG_LEVEL=DEBUG`. All consumer modules route through it.
- **Tests**: 6 capture tests in `tests/test_capture_and_return.py` +
  existing history tests still pass. Suite: 83 pass, 1 pre-existing
  unrelated failure (`test_empty_texto_sical_handling` — user said leave).

### Orchestrator (`sical-robot/`)

- **`src/services/contableAssembly.js`** (NEW): decode/verify → persist →
  merge (contable first, pooled attachments after) → print → stage
  portafirmas. Retries for transient I/O; `assembly_status` lifecycle.
  Exports `assembleFromResult`, `recover`, `reassemble`.
- **`src/database.js`**: new `task_contable_documents` table
  (PK=`task_id`, owns the `assembly_status` lifecycle —
  intentional deviation from spec §8 because the lifecycle starts at
  contable receipt, before any merged row exists). Methods:
  `saveContableDocument`, `getContableDocument`, `setContableAssembly`,
  `getContableDocsByAssemblyStatus`. `getTasksWithStatistics` now joins
  `task_contable_documents` and returns `assembly_status`,
  `contable_capture_status`, `assembly_error`.
- **`src/main.js`**:
  - `DEFAULT_APP_SETTINGS` + `app-settings.json` got
    `contableAssemblyEnabled` and a `contableAssembly` block
    (`portafirmasDir`, `printerName`, `assemblyRetries`,
    `assemblyBackoffMs`).
  - Inject `printPdfSilently(absPath, deviceName)` — hidden
    `BrowserWindow` + `webContents.print({silent:true, …})`.
    **UNVERIFIED.**
  - `taskResult` handler: when flag ON and `result.contable_document`
    present, call `contableAssembly.assembleFromResult(...)`, broadcast
    `task-status-updated` with `{assembly:{status,error}}`.
  - Startup recovery hook calls `contableAssembly.recover()`.
  - New IPC `reassemble-contable` for the operator action.
- **`src/taskMonitor.js` + CSS**: assembly badge
  (`📄/🧩/🖨/✅/⚠`) in the status cell; 🧩 re-assemble action button
  on `FAILED` rows. (Earlier in the session also added: type-to-confirm
  🗑️ delete with cascade to task-id-referencing tables, button-overflow
  fix via `flex-wrap` + widened Actions column.)

### Ancillary fixes shipped in the same session

- **Task delete in Task Monitor** ([taskMonitor.js], [main.js],
  [database.js]) — type-to-confirm modal, in-flight warning when
  PUBLISHED/PROCESSING, and **cascade delete** across all
  task-referencing tables (`accounting_tasks`, `liquidation_files`,
  `task_merged_documents`, `task_document_assignments`,
  `attachment_ack_log`). Memory saved:
  `memory/feedback_task_delete_cascade.md`.
- **Arqueo fecha guardrail** ([main.js] `buildOperationData` +
  `publish-task-manually`) — strips `/` from the fecha actually
  published to the consumer (the SICAL date field is `/`-masked), while
  the DB row / liquidation validator keep canonical `DD/MM/YYYY`. Memory:
  `memory/project_arqueo_fecha_no_slash.md`.
- **One-off DB cleanup**: purged the stranded `liquidation_files` row
  (and orphan attachment rows) for the deleted task
  `203_05052026_159.6_comerc_0` — see chat for the exact script; live
  task `203_05052026_159.6_comerc` (no `_0`) is intact and unaffected.
- **Arqueos GUI** — fixed Attachment row overlapping the Status row
  (`row=9` collision); the Contable row is now row 9, Status row 10.

## 4. Activation state

| Side | Flag | Value | Where |
|---|---|---|---|
| consumer | `CONTABLE_CAPTURE_ENABLED` | `true` (default) | `arqueos_robot/config.py` (override via env var or `.env`) |
| orchestrator | `contableAssemblyEnabled` | `true` | `sical-robot/src/data/app-settings.json` |

Both ON together is required — when consumer capture is ON it **no
longer prints in SICAL**; if sical assembly were OFF, nothing would
print. Rollback by flipping both back to false; never leave them split.

## 5. UNVERIFIED hotspots (must be validated on a live SICAL run)

1. **`arqueos_robot/doc_pipeline/sical_capture.py`** — every SICAL
   selector ("Documento" button, `FseleccionTipoDoc`, Talón de Cargo
   checkbox at `1|3`, deselect carta de pago at `1|4`, Guardar PDF
   `2|2|3`, "Guardar como" dialog `EditControl name:"Nombre:"` +
   `Button name:"Guardar"`, overwrite Yes/runtime-error modals, Salir
   `2|2|6`). Ported from older-version legacy code; no test env.
2. **`sical-robot/src/main.js` `printPdfSilently`** — Electron silent
   PDF print via hidden BrowserWindow + `webContents.print({silent:true,
   deviceName})`. Untested with a real printer.
3. **Capture failure mode**: since the consumer no longer does the
   legacy in-app print when the capture path is ON, a wrong selector =
   no printed document for that task. SICAL operation is unaffected
   (committed at validate). Operator sees `capture_status=FAILED` /
   `assembly_status=FAILED`; can fix selector + roll back, or accept
   manual handling.

See `docs/contable-assembly-dry-run.md` for the one-task validation
runbook.

## 6. Locked design decisions (from the interactive Q&A)

| Decision | Choice |
|---|---|
| Printing locus | sical-robot prints all finalized tasks (uniform) |
| Merge failure (attachment bound) | Retry transient I/O 3× then surface in Task Monitor — no silent contable-only fallback |
| Return transport | Inline base64 in result message; `MAX_INLINE_BYTES` ≈ 2 MB guard (storage_ref fallback not built — would only matter for outsized docs) |
| Consumer module sharing | Vendored copy in each robot (no shared package) — relevant for Phase B′ |
| Data model | Dedicated `task_contable_documents` table; `assembly_status` lives there (not on `task_merged_documents`, despite §8 wording — see spec note) |
| Rollout default | OFF originally; user flipped both flags ON to activate |
| Retries | 3 attempts, short backoff (1500 ms), configurable |
| Gastos doc | Same pattern as arqueo (ADO doc), selectors UNVERIFIED, Phase B′ |

## 7. Memories

(in `C:\Users\antonioalvarez\.claude\projects\C--Users-antonioalvarez-desarrollo-python-ayto-automatiza-v10-rabbit-sical-robot\memory\`)

- `feedback_liquidation_validation.md` — strict-integrity preference;
  fix source data, don't loosen validation.
- `feedback_task_delete_cascade.md` — task deletion must purge all
  task_id-referencing tables.
- `project_arqueo_fecha_no_slash.md` — strip `/` from arqueo fecha at
  publish; keep DB/validation canonical `DD/MM/YYYY`.

## 8. Recommended next steps

1. **Live dry-run** (when a SICAL test/staging env is available):
   walk through `docs/contable-assembly-dry-run.md` on one finalized
   arqueo. Capture-only first, then with one attachment, then a
   restart-recovery scenario, then a rollback test.
2. **Verify or fix `sical_capture.py` selectors** against the current
   SICAL build. Most likely culprit on first failure.
3. **Verify `printPdfSilently`** with the operator's actual printer
   (the `printerName` setting in `app-settings.json`).
4. **Phase B′ (gastos)** — mirror the arqueo capture+return contract in
   `gastos_robot/`. Decisions already locked: vendored copy of the
   capture helper, same envelope shape, ADO document target. sical-robot
   side is consumer-agnostic — should need no changes.
5. Optional: address the pre-existing `test_empty_texto_sical_handling`
   failure (user explicitly chose to leave it).

## 9. Quick reference

### Sample of the new log stream (consumer)

```
14:51:52 INFO  task=203_05052026_159.6.. RECEIVED   arqueo task ...comerc_0 (corr=ab12)
14:51:52 INFO  task=203_05052026_159.6.. PARSED     op#- importe=159.6 fecha=05/05/2026 caja=203_CRURAL nat=4 lineas=2
14:51:52 INFO  task=203_05052026_159.6.. DUP-CHECK  no similar records - proceeding
14:51:52 INFO  task=203_05052026_159.6.. SICAL-OPEN arqueo window open
14:51:52 INFO  task=203_05052026_159.6.. FILL       writing main panel + 2 aplicacion line(s)
14:51:52 INFO  task=203_05052026_159.6.. VALIDATE   operation validated -> num_operacion=26000777
14:51:52 INFO  task=203_05052026_159.6.. CONTABLE   captured 2p / 41213 B / sha=9f3c1a2b... -> returning to producer
14:51:52 INFO  task=203_05052026_159.6.. RESULT     returning contable 2p / 41213 B to producer
14:51:52 INFO  task=203_05052026_159.6.. DONE       COMPLETED (op#26000777, 0:00:42)
14:51:52 ERROR task=203_05052026_159.6.. CONTABLE   FAILED at CONTABLE -- sical_capture: Guardar como window not found
```

### Useful paths

- Main DB (sical-robot): `sical-robot/src/data/db/prueba05.sqlite`
- Attachments storage base: `<userData>/attachments/`
- Portafirmas outbox: `~/SicalRobot/portafirmas_outbox/<task_id>.{pdf,json}`
- Capture workdir (consumer): `arqueos_robot/data/doc_work/`
- Consumer history DB: `arqueos_robot/arqueos_history.db`

### Read-only SQL for a single task

```sql
SELECT task_id, capture_status, assembly_status, assembly_error,
       merged_document_id, staged_path
  FROM task_contable_documents WHERE task_id = ?;

SELECT id, sha256, size_bytes, page_count, storage_key
  FROM task_merged_documents WHERE task_id = ?;
```

### Rollback (both, together)

```
arqueos_robot/.env  ->  CONTABLE_CAPTURE_ENABLED=false
sical-robot/src/data/app-settings.json -> "contableAssemblyEnabled": false
```
…then restart both apps.

### Re-assemble from Task Monitor

Press the 🧩 button on a `FAILED` row → calls `reassemble-contable`
IPC → reads the stored contable PDF and re-runs merge→print→stage from
it (no SICAL re-run). Useful after fixing a printer/stage issue.
A *capture* failure has no stored contable; re-publish/retry the task.
