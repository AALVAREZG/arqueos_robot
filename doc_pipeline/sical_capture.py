"""
SICAL UI driver: save the Talon de Cargo as a PDF file.

============================ !!! UNVERIFIED !!! ============================
Every window regex and element selector below is a direct port of legacy
code written against an OLDER SICAL build. NONE of it has been validated
against the current SICAL version. Treat every ``.find(...)`` here as a
hypothesis to confirm during the SICAL dry-run before production use.
See docs/attachment-finalization-spec.md sections 6.4 and 10.

Until verified, attachment-bearing arqueos will most likely fall back to
the "FAILED" ack path (the SICAL operation itself is unaffected -- it is
already committed by validate_operation() before this runs).
===========================================================================
"""

import logging
import os
import time

from robocorp import windows

from sical_ui_utils import wait_for_window

logger = logging.getLogger(__name__)


class SicalCaptureError(Exception):
    """Raised when the SICAL document could not be saved to PDF."""


_VISOR_REGEX = 'regex:.*Visualizador de Documentos de SICAL v2'


def _close_visualizador(visor=None, attempts=3):
    """
    Best-effort close of the 'Visualizador de Documentos de SICAL v2' window.

    Idempotent and never raises: the contable PDF is already saved by the time
    we get here, so failing to close the viewer must not fail the capture.

    When SICAL saves the document it auto-opens it, which **minimizes** the
    Visualizador. A minimized window's UI tree is not interactable, so the
    Salir button (``2|2|6``) can't be found/clicked until the window is
    restored. Each attempt therefore: re-finds the window fresh (the handle
    grabbed before the 'Guardar como' dialog may be stale), restores +
    foregrounds it, clicks Salir, answers a possible exit-confirmation
    dialog, and -- if the button is unreachable -- falls back to a direct
    window close. Closure is verified before giving up.
    """
    for i in range(attempts):
        try:
            # Re-find fresh; fall back to the handle we already had.
            win = windows.find_window(
                _VISOR_REGEX, timeout=2.0, raise_error=False) or visor
            if win is None:
                return  # already closed

            # Un-minimize + bring to front so its controls become interactable.
            try:
                win.restore_window()
                win.foreground_window()
                time.sleep(0.5)
            except Exception as exc:  # noqa: BLE001 - best-effort
                logger.warning(
                    "restore/foreground Visualizador failed: %s", exc)

            salir = win.find(
                'class:"TBitBtn" and path:"2|2|6"', raise_error=False)
            if salir:
                salir.click(wait_time=0.5)
                time.sleep(0.5)
                # Some builds prompt "¿Desea salir?" -> click affirmative.
                for confirm in ('Yes', 'Sí', 'Si'):
                    btn = win.find(
                        f'class:"TButton" and name:"{confirm}"',
                        raise_error=False)
                    if btn:
                        btn.click(wait_time=0.5)
                        break
            else:
                # Salir not reachable -> close the window directly (WM_CLOSE).
                logger.warning(
                    "Salir button not found; closing Visualizador directly")
                win.close_window()
        except Exception as exc:  # noqa: BLE001 - closing is best-effort
            logger.warning(
                "close Visualizador attempt %d/%d failed: %s",
                i + 1, attempts, exc)

        # Verify the window is gone; if so we are done.
        still_open = windows.find_window(
            _VISOR_REGEX, timeout=1.0, raise_error=False)
        if still_open is None:
            return

    logger.warning(
        "Visualizador de Documentos still open after %d close attempt(s)",
        attempts)


def capture_sical_pdf(ventana_arqueo, num_operacion, dest_dir):
    """
    From the arqueo window: open Documento -> select Talon de Cargo ->
    open the Visualizador -> Guardar PDF -> drive the 'Guardar como'
    dialog to ``<dest_dir>\\<num_operacion>_sical.pdf``. Returns that path.

    Raises :class:`SicalCaptureError` on any failure. The caller treats this
    as a non-fatal, attachment-only failure.
    """
    if not num_operacion:
        raise SicalCaptureError("num_operacion is empty; cannot name the PDF")

    os.makedirs(dest_dir, exist_ok=True)
    pdf_path = os.path.join(dest_dir, f"{num_operacion}_sical.pdf")

    visor = None
    try:
        # --- Open the document-type selector ------------------------------
        # Reuse the window if it is already open; otherwise click Documento
        # and poll for FseleccionTipoDoc to appear (robocorp's own timeout
        # parameter is not reliably honoured -- we drive the wait ourselves).
        ventana_tipo = wait_for_window(
            'regex:.*FseleccionTipoDoc', timeout=0.5)
        if not ventana_tipo:
            ventana_arqueo.find('class:"TBitBtn" and name:"Documento"').click()
            ventana_tipo = wait_for_window(
                'regex:.*FseleccionTipoDoc', timeout=20.0)
        if not ventana_tipo:
            raise SicalCaptureError(
                'FseleccionTipoDoc window did not open within 20s')
        ventana_tipo.find(
            'class:"TCheckBox" and path:"1|3" and name:"Talón de Cargo"'
        ).click()
        time.sleep(0.05)
        # UNVERIFIED: deselect "carta de pago"
        ventana_tipo.find('class:"TCheckBox" and path:"1|4"').click()
        time.sleep(0.05)
        ventana_tipo.find(
            'class:"TButton" and name:"OK" and path:"1|2"').click()
        time.sleep(1)

        # --- UNVERIFIED: Visualizador -> Guardar PDF ----------------------
        visor = windows.find_window(_VISOR_REGEX)
        # UNVERIFIED: legacy says path "2|2|3"; an old comment referenced
        # "2|2|2". Confirm during the dry-run.
        visor.find('class:"TBitBtn" and path:"2|2|3"').click()  # Guardar PDF

        # --- UNVERIFIED: 'Guardar como' Windows dialog --------------------
        save_as = windows.find_window(
            'regex:.*Guardar como', timeout=5.0, raise_error=False)
        if save_as:
            time.sleep(2)
            save_as.find(
                'control:"EditControl" and name:"Nombre:"'
            ).set_value(pdf_path)
            time.sleep(1)
            save_as.find('class:"Button" and name:"Guardar"').click()

        # UNVERIFIED: overwrite confirmation (file already exists).
        overwrite_yes = visor.find(
            'class:"TButton" and name:"Yes" and path:"1|2"',
            raise_error=False)
        if overwrite_yes:
            overwrite_yes.click(wait_time=0.5)
            runtime_aceptar = visor.find(
                'class:"TButton" and name:"Aceptar"', raise_error=False)
            if runtime_aceptar:
                runtime_aceptar.click(wait_time=0.5)

        # UNVERIFIED: occasional runtime-error modal after save.
        runtime_ok = visor.find(
            'class:"TButton" and name:"OK"', raise_error=False)
        if runtime_ok:
            runtime_ok.click(wait_time=0.5)

    except Exception as exc:  # noqa: BLE001 - normalize to one error type
        raise SicalCaptureError(f"SICAL capture failed: {exc}") from exc
    finally:
        # Always close the Visualizador so windows don't pile up across tasks.
        # Best-effort and never raises (the PDF is already saved on the
        # success path; on the failure path the viewer may still be open).
        _close_visualizador(visor)

    # Give the writer a moment, then confirm the file landed.
    for _ in range(10):
        if os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0:
            return pdf_path
        time.sleep(0.5)
    raise SicalCaptureError(f"expected PDF not found after save: {pdf_path}")
