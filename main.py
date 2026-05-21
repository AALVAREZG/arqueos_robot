
from logging_setup import configure_logging, get_logger, phase as log_phase
from arqueo_task_consumer import ArqueoConsumer


def main():
    # Single centralized, phase-oriented logging (see logging_setup.py).
    # Set ARQUEOS_LOG_LEVEL=DEBUG for verbose internals.
    configure_logging()
    logger = get_logger(__name__)
    log_phase(logger, 'CONN', 'Arqueos Robot starting (headless)')

    consumer = ArqueoConsumer()
    try:
        consumer.start_consuming()
    except Exception:
        consumer.stop_consuming()


if __name__ == "__main__":
    main()