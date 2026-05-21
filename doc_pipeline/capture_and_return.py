"""
Capture the SICAL contable PDF and build the `contable_document` envelope
returned to sical-robot in the result message (spec v2 §2.2).

Transport: inline base64 by default. If the PDF exceeds the configured
inline limit a `storage_ref` would be required, but the consumer no longer
has a storage backend (stripped in Phase A'), so an oversize doc is
reported as a capture failure rather than silently dropped. A Talon de
Cargo is 1-2 pages / tens of KB, so this is a safety net, not a path.

Never raises: the SICAL operation is already committed before this runs;
any failure here only sets capture_status=FAILED on the envelope.
"""

import base64
import hashlib
import os

from .sical_capture import capture_sical_pdf, SicalCaptureError
from logging_setup import get_logger, detail as log_detail

# Internal detail only: the clean CONTABLE ok/FAILED line is emitted by
# arqueo_tasks.finalize_capture; here we only add DEBUG breadcrumbs and the
# precise failure reason (which also rides out on envelope.capture_error).
logger = get_logger(__name__)


def _page_count(pdf_path):
    try:
        from pypdf import PdfReader
        return len(PdfReader(pdf_path).pages)
    except Exception as exc:  # noqa: BLE001 - page count is a soft signal
        log_detail(logger, 'CONTABLE', f'page_count unavailable: {exc}')
        return None


def capture_and_return(ventana_arqueo, num_operacion, cfg):
    """
    Returns the `contable_document` envelope dict:

        {filename, mime_type, page_count, size_bytes, sha256,
         transport: "inline_base64", data: "<b64>",
         capture_status: "CAPTURED"|"FAILED", capture_error: str|None}

    On any failure, capture_status="FAILED", data=None, capture_error set.
    """
    envelope = {
        'filename': f'{num_operacion}.pdf' if num_operacion else 'contable.pdf',
        'mime_type': 'application/pdf',
        'page_count': None,
        'size_bytes': None,
        'sha256': None,
        'transport': 'inline_base64',
        'data': None,
        'capture_status': 'FAILED',
        'capture_error': None,
    }

    try:
        pdf_path = capture_sical_pdf(
            ventana_arqueo, num_operacion, cfg.SICAL_PDF_WORKDIR)
    except SicalCaptureError as exc:
        envelope['capture_error'] = f'sical_capture: {exc}'
        log_detail(logger, 'CONTABLE', envelope['capture_error'])
        return envelope
    except Exception as exc:  # noqa: BLE001 - never raise out of finalize
        envelope['capture_error'] = f'sical_capture (unexpected): {exc}'
        log_detail(logger, 'CONTABLE', envelope['capture_error'])
        return envelope

    try:
        with open(pdf_path, 'rb') as fh:
            data = fh.read()
        size = len(data)
        envelope['size_bytes'] = size
        envelope['sha256'] = hashlib.sha256(data).hexdigest()
        envelope['page_count'] = _page_count(pdf_path)

        max_inline = int(getattr(cfg, 'MAX_INLINE_BYTES', 2 * 1024 * 1024))
        if size > max_inline:
            envelope['capture_error'] = (
                f'contable PDF {size} bytes exceeds inline limit '
                f'{max_inline}; storage_ref transport not configured on '
                f'the consumer (Phase A′)')
            log_detail(logger, 'CONTABLE', envelope['capture_error'])
            return envelope

        envelope['data'] = base64.b64encode(data).decode('ascii')
        envelope['capture_status'] = 'CAPTURED'
        log_detail(logger, 'CONTABLE',
                   f"encoded {size} B / {envelope['page_count']} pages / "
                   f"sha={(envelope['sha256'] or '')[:12]}")
        return envelope
    except Exception as exc:  # noqa: BLE001
        envelope['capture_error'] = f'read/encode: {exc}'
        log_detail(logger, 'CONTABLE', envelope['capture_error'])
        return envelope
