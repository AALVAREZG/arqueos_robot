# Live dry-run checklist — inverted contable assembly (Phase A′, arqueo)

Cross-project (sical-robot + arqueos_robot). Goal: confirm the two
UNVERIFIED hotspots on **one** finalized arqueo before trusting it for
volume:

1. `arqueos_robot/doc_pipeline/sical_capture.py` — the SICAL "Guardar PDF"
   → "Guardar como" UI selectors.
2. `sical-robot` `printPdfSilently` — Electron silent PDF print.

Reminder: with the capture path ON the consumer **no longer prints in
SICAL**. If capture fails, that task's document is printed nowhere until
fixed or rolled back. The SICAL accounting operation itself is unaffected
(committed at validate, before capture).

## 0. Pre-flight

- [ ] `arqueos_robot/.env` has no `CONTABLE_CAPTURE_ENABLED=false`; config
      resolves `True` (`python -c "import config; print(config.CONTABLE_CAPTURE_ENABLED)"`).
- [ ] `sical-robot/src/data/app-settings.json`: `contableAssemblyEnabled: true`,
      `attachmentsEnabled: true`.
- [ ] `contableAssembly.printerName` — set to the exact Windows printer name,
      or leave `""` for the system default. Confirm a default printer exists
      on the **sical-robot host** (printing now happens there, not on the
      robot box).
- [ ] Dirs writable: `arqueos_robot/data/doc_work` (capture),
      `~/SicalRobot/portafirmas_outbox` (staging). Both are auto-created;
      just confirm the parent is writable.
- [ ] **Restart both apps** (flags read at startup).
- [ ] Have a backup of `sical-robot/src/data/db/prueba05.sqlite`.

## 1. Pick a low-risk task

- One arqueo, finalized (`_FIN`), small. Ideally **with one attachment
  bound** (to exercise the merge), and separately one **without** (contable-
  only path). Avoid a liquidation/"facturacion comercio" task for the first
  run (more moving parts).

## 2. Watch the consumer (arqueos_robot)

During processing, in the Arqueos GUI **Current Task** panel:

- [ ] `Status:` advances to `Capturing contable document`.
- [ ] `Contable:` row ends as `✅ <num>.pdf (Np, NB) [CAPTURED]`
      (not `⚠️ ... [FAILED]`).

Consumer log lines to grep:

- Success: `Contable captured: <bytes> bytes, <pages> pages, sha=<...>`
- Selector failure: `sical_capture: SICAL capture failed: ...` or
  `expected PDF not found after save: ...`

If `[FAILED]` here → the §1 hotspot (SICAL selectors). Note the exact
`capture_error`; that text points at which `.find(...)` in
`sical_capture.py` missed. Do **not** keep running tasks — fix selectors
or roll back first.

## 3. Watch the result hop

- [ ] Task Monitor (sical-robot) row for the task: the **assembly badge**
      appears next to the RabbitMQ badge and progresses:
      `📄 Contable recibido → 🧩 Fusionado → 🖨 Impreso → ✅ En portafirmas`.
- [ ] Final badge is `✅ En portafirmas`. `⚠ Ensamblado falló` = stop and
      read the error (hover tooltip shows `assembly_error`).

sical-robot console log lines:

- End-to-end OK: `[contableAssembly] task <id> STAGED -> <path>`
- Verify failure (corrupt/truncated transfer): `decode/verify failed: ...`
- Merge/print/stage retry exhaustion: `[contableAssembly] <merge|print|stage> attempt n/3 failed: ...` then `assembly failed: ...`

## 4. Inspect the artifacts

Portafirmas outbox (`~/SicalRobot/portafirmas_outbox`):

- [ ] `<task_id>.pdf` exists and **opens**; page 1 is the SICAL contable
      doc, attachment pages (if any) appended **after**.
- [ ] `<task_id>.json` sidecar present with `contable_sha256`,
      `merged_document_id`, `staged_at`.
- [ ] The PDF actually **came out of the printer** (the only non-inspectable
      step — physically check).

DB (read-only) — `sical-robot/src/data/db/prueba05.sqlite`:

```sql
SELECT task_id, capture_status, assembly_status, assembly_error,
       merged_document_id, staged_path
FROM task_contable_documents WHERE task_id = '<task_id>';
-- expect: CAPTURED / STAGED / NULL error / non-null merged_document_id+staged_path

SELECT id, sha256, size_bytes, page_count, storage_key
FROM task_merged_documents WHERE task_id = '<task_id>';
-- the final merged artifact row
```

Stored contable copy: `<attachments base>/contable/<task_id>/<sha256>.pdf`.

## 5. Failure-point cheat sheet

| Symptom | Where | Likely cause |
|---|---|---|
| Consumer `Contable: [FAILED]`, error mentions `Guardar como`/`find` | sical_capture.py | UNVERIFIED selector wrong on this SICAL build |
| `task_contable_documents.assembly_status=FAILED`, error `decode/verify` | transport | base64/sha/size mismatch (rare; integrity guard working) |
| Stuck at `MERGED`, error in `print` retries | printPdfSilently | Electron silent print / printer name / driver |
| Stuck at `PRINTED`, error in `stage` | stager | portafirmas dir not writable |
| No badge at all, consumer printed nothing | both flags | one side OFF, or task not `_FIN` |

## 6. Recovery check (optional)

Mid-run, with a task at `MERGED`/`PRINTED` (not STAGED), kill and restart
sical-robot. Expect log `✅ Contable-assembly recovery: { recovered: N }`
and the badge reaching `✅ En portafirmas` without re-running SICAL.

## 7. Re-assemble action

For a `FAILED` row, the 🧩 button (Task Monitor) re-runs
merge→print→stage from the stored contable PDF (no SICAL re-run). Use it
after fixing a printer/stage issue. (A capture failure can't be
re-assembled — there's no stored contable; re-run/retry the task instead.)

## 8. Rollback (both, together)

- `arqueos_robot/.env`: `CONTABLE_CAPTURE_ENABLED=false`
- `sical-robot/src/data/app-settings.json`: `"contableAssemblyEnabled": false`
- Restart both. Consumer returns to legacy in-app SICAL print; sical-robot
  ignores any `contable_document`. Never leave the two flags split.

## 9. Sign-off

- [ ] Contable-only task: printed + staged + `STAGED`.
- [ ] Task with attachment: merged order correct + printed + staged.
- [ ] Recovery resumes after restart.
- [ ] Rollback verified to restore legacy print.

Only after all four: trust it for normal volume. Then plan Phase B′
(gastos) reusing the same contract.
