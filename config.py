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