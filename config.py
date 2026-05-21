# config.py
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Determine the directory where the executable/script is located
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    application_path = Path(sys.executable).parent
else:
    # Running as script
    application_path = Path(__file__).parent

# Look for .env file in the application directory
env_path = application_path / '.env'

# Load .env file if it exists, otherwise use environment variables or defaults
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # Try to load from current working directory as fallback
    load_dotenv()

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')


# ---------------------------------------------------------------------------
# Contable-document capture (inverted architecture, spec v2)
# See docs/attachment-finalization-spec.md
# ---------------------------------------------------------------------------

def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


# Rollout guard. ACTIVATED: the consumer captures the contable PDF and
# returns it instead of the legacy in-app print. Must stay ON in tandem
# with sical-robot's contableAssemblyEnabled (both ON together), otherwise
# the document is captured but never printed/staged. Set the env var
# CONTABLE_CAPTURE_ENABLED=false to roll back without a code change.
CONTABLE_CAPTURE_ENABLED = _as_bool(
    os.getenv('CONTABLE_CAPTURE_ENABLED', 'true'), True)

# Where SICAL's "Guardar como" dialog writes <num_operacion>_sical.pdf.
# Must be writable by SICAL.
SICAL_PDF_WORKDIR = os.getenv(
    'SICAL_PDF_WORKDIR',
    str(application_path / 'data' / 'doc_work'),
)

# Inline-base64 size guard for the returned contable PDF. Above this the
# consumer reports a capture failure (no storage backend on the consumer in
# Phase A'); a Talon de Cargo is far below this.
MAX_INLINE_BYTES = int(os.getenv('MAX_INLINE_BYTES', 2 * 1024 * 1024))