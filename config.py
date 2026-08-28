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


# RESERVA, ya no interruptor.
#
# La decision de que hacer con el documento la toma ahora el productor y viaja
# en el mensaje, en `parameters.document_mode` (ver document_mode.py y la spec
# `sical-robot/docs/document-robot-split-spec.md`, §4). Este valor solo se
# consulta cuando el mensaje NO trae el campo -consumidor nuevo contra
# productor viejo-, que es lo que permite desplegar el productor primero.
#
# Se retira cuando los tres consumidores entiendan el campo. Mientras tanto
# conserva su significado antiguo: ON = capturar y devolver, OFF = imprimir en
# SICAL. Sigue en ON porque asi estaba, no porque decida nada nuevo.
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