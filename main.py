
import logging
from arqueo_task_consumer import ArqueoConsumer

def setup_logger(name: str = 'Sical arqueos', level: int = logging.DEBUG) -> logging.Logger:
    """Setup a simple console logger"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create console handler if not already added
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

def main():
    logger = setup_logger(name="Sical arqueos", level=logging.DEBUG)
    consumer = ArqueoConsumer()
    try:
        print("init...")
        consumer.start_consuming()
    except Exception as e:
        consumer.stop_consuming()

if __name__ == "__main__":
    main()