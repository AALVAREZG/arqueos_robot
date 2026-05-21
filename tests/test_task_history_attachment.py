"""
Tests for attachment_info persistence in task_history_db:
round-trip on save/update and additive migration of a pre-existing DB.
"""

import json
import sqlite3
from datetime import datetime

import pytest

from task_history_db import TaskHistoryDB


def _started_row(task_id, attachment_info=None):
    return {
        'task_id': task_id,
        'operation_number': 'OP1',
        'amount': 10.0,
        'date': '01/01/2026',
        'cash_register': '001',
        'third_party': 'X',
        'nature': '4',
        'description': 'd',
        'total_line_items': 1,
        'status': 'processing',
        'started_at': datetime.now(),
        'completed_at': None,
        'duration_seconds': None,
        'error_message': None,
        'raw_data': {},
        'attachment_info': attachment_info,
    }


class TestAttachmentPersistence:
    @pytest.mark.unit
    def test_save_then_complete_roundtrip(self, tmp_path):
        db = TaskHistoryDB(db_path=str(tmp_path / 'h.db'))
        info = json.dumps({'filename': 't1.pdf', 'transport': 's3_presigned',
                           'status': None})
        db.save_task(_started_row('t1', info))

        # Final ack arrives on completion.
        final = json.dumps({'filename': 't1.pdf', 'transport': 's3_presigned',
                            'status': 'ATTACHED', 'error': None})
        db.update_task_status('t1', 'completed',
                              completed_at=datetime.now(),
                              duration_seconds=1.0,
                              attachment_info=final)

        row = db.get_task_by_id('t1')
        assert json.loads(row['attachment_info'])['status'] == 'ATTACHED'

    @pytest.mark.unit
    def test_update_without_attachment_keeps_existing(self, tmp_path):
        db = TaskHistoryDB(db_path=str(tmp_path / 'h.db'))
        info = json.dumps({'filename': 'keep.pdf', 'status': None})
        db.save_task(_started_row('t2', info))

        # No-attachment task completion must not wipe the column.
        db.update_task_status('t2', 'completed',
                              completed_at=datetime.now(),
                              duration_seconds=1.0,
                              attachment_info=None)

        row = db.get_task_by_id('t2')
        assert json.loads(row['attachment_info'])['filename'] == 'keep.pdf'

    @pytest.mark.unit
    def test_no_attachment_is_null(self, tmp_path):
        db = TaskHistoryDB(db_path=str(tmp_path / 'h.db'))
        db.save_task(_started_row('t3', None))
        assert db.get_task_by_id('t3')['attachment_info'] is None

    @pytest.mark.unit
    def test_additive_migration_on_legacy_db(self, tmp_path):
        # Build a legacy task_history table WITHOUT attachment_info.
        legacy = tmp_path / 'legacy.db'
        conn = sqlite3.connect(legacy)
        conn.execute("""
            CREATE TABLE task_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                operation_number TEXT, amount REAL, date TEXT,
                cash_register TEXT, third_party TEXT, nature TEXT,
                description TEXT, total_line_items INTEGER, status TEXT,
                started_at TIMESTAMP, completed_at TIMESTAMP,
                duration_seconds REAL, error_message TEXT, raw_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "INSERT INTO task_history (task_id, status) VALUES ('old', 'completed')")
        conn.commit()
        conn.close()

        # Opening via TaskHistoryDB must add the column without data loss.
        db = TaskHistoryDB(db_path=str(legacy))
        cols = {r[1] for r in sqlite3.connect(legacy).execute(
            "PRAGMA table_info(task_history)")}
        assert 'attachment_info' in cols
        old = db.get_task_by_id('old')
        assert old is not None and old['attachment_info'] is None
