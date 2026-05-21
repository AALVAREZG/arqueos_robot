"""
Unit tests for the contable-capture envelope (spec v2). The SICAL UI
driver (sical_capture) is monkeypatched out; these cover the envelope:
success (base64 + metadata), capture failure, and the inline size guard.
"""

import base64
import hashlib
import json
import os
from types import SimpleNamespace

import pytest

from doc_pipeline import capture_and_return as car
from doc_pipeline.sical_capture import SicalCaptureError
from arqueo_tasks import OperationResult, OperationStatus, OperationEncoder


def _make_pdf(path):
    pypdf = pytest.importorskip('pypdf')
    w = pypdf.PdfWriter()
    w.add_blank_page(width=200, height=200)
    with open(path, 'wb') as fh:
        w.write(fh)
    return path


def _cfg(tmp_path, max_inline=2 * 1024 * 1024):
    return SimpleNamespace(
        SICAL_PDF_WORKDIR=str(tmp_path / 'work'),
        MAX_INLINE_BYTES=max_inline,
    )


class TestCaptureAndReturn:
    @pytest.mark.unit
    def test_success_envelope(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        os.makedirs(cfg.SICAL_PDF_WORKDIR, exist_ok=True)
        pdf = _make_pdf(os.path.join(cfg.SICAL_PDF_WORKDIR, 'OP1_sical.pdf'))
        raw = open(pdf, 'rb').read()

        monkeypatch.setattr(car, 'capture_sical_pdf',
                            lambda v, num, d: pdf)

        env = car.capture_and_return(None, 'OP1', cfg)

        assert env['capture_status'] == 'CAPTURED'
        assert env['capture_error'] is None
        assert env['filename'] == 'OP1.pdf'
        assert env['mime_type'] == 'application/pdf'
        assert env['transport'] == 'inline_base64'
        assert env['size_bytes'] == len(raw)
        assert env['sha256'] == hashlib.sha256(raw).hexdigest()
        assert base64.b64decode(env['data']) == raw
        assert env['page_count'] == 1

    @pytest.mark.unit
    def test_capture_failure(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)

        def boom(v, num, d):
            raise SicalCaptureError('Visualizador not found')

        monkeypatch.setattr(car, 'capture_sical_pdf', boom)
        env = car.capture_and_return(None, 'OP2', cfg)

        assert env['capture_status'] == 'FAILED'
        assert env['data'] is None
        assert 'sical_capture' in env['capture_error']

    @pytest.mark.unit
    def test_oversize_guard(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, max_inline=10)  # tiny limit
        os.makedirs(cfg.SICAL_PDF_WORKDIR, exist_ok=True)
        pdf = _make_pdf(os.path.join(cfg.SICAL_PDF_WORKDIR, 'OP3_sical.pdf'))
        monkeypatch.setattr(car, 'capture_sical_pdf', lambda v, n, d: pdf)

        env = car.capture_and_return(None, 'OP3', cfg)

        assert env['capture_status'] == 'FAILED'
        assert env['data'] is None
        assert 'exceeds inline limit' in env['capture_error']
        # Metadata still computed even when over the guard.
        assert env['size_bytes'] > 10
        assert env['sha256']

    @pytest.mark.unit
    def test_unexpected_capture_error_is_swallowed(self, tmp_path,
                                                   monkeypatch):
        cfg = _cfg(tmp_path)

        def kaboom(v, n, d):
            raise RuntimeError('COM blew up')

        monkeypatch.setattr(car, 'capture_sical_pdf', kaboom)
        env = car.capture_and_return(None, 'OP4', cfg)
        assert env['capture_status'] == 'FAILED'
        assert 'unexpected' in env['capture_error']


class TestCaptureAckSerialization:
    @pytest.mark.unit
    def test_operation_result_serializes_capture_fields(self):
        r = OperationResult(
            status=OperationStatus.COMPLETED,
            init_time='t0',
            num_operacion='OP42',
            capture_status='CAPTURED',
            capture_error=None,
        )
        decoded = json.loads(json.dumps(r, cls=OperationEncoder))
        assert decoded['capture_status'] == 'CAPTURED'
        assert decoded['capture_error'] is None
        # The base64 payload is carried out-of-band, NOT in the dataclass.
        assert 'data' not in decoded

    @pytest.mark.unit
    def test_default_result_has_no_capture(self):
        r = OperationResult(status=OperationStatus.COMPLETED, init_time='t0')
        decoded = json.loads(json.dumps(r, cls=OperationEncoder))
        assert decoded['capture_status'] is None
