import logging
import os
from datetime import datetime
import sys


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(message)s"))
handler.setLevel(logging.INFO)
handler.stream.reconfigure(encoding="utf-8")


def setup_logging():
    """Setup logging configuration for the application."""

    # Create logs directory if it doesn't exist
    log_dir = "logs/"
    os.makedirs(log_dir, exist_ok=True)

    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir + f"bank_statement_extraction_{timestamp}.log"
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode="a"),
            logging.StreamHandler(),  # Also log to console
        ],
    )

    return logging.getLogger(__name__)


def get_logger(name=None, page_num=None):
    """Get a logger instance."""
    if name is None:
        name = __name__

    if page_num is not None:
        name = f"page_{page_num}"

    return logging.getLogger(name)


def setup_logging_for_each_page(storage_dir, page_num):
    """Setup logging configuration for each page and return page-specific logger."""

    os.makedirs(storage_dir, exist_ok=True)

    page_specific_log_dir = f"{storage_dir}/logs"
    os.makedirs(page_specific_log_dir, exist_ok=True)

    # Create unique logger name for this page
    page_name = storage_dir.split("/")[-1]
    logger_name = f"{page_name}_page_{page_num}"
    page_logger = logging.getLogger(logger_name)

    # Only add handlers if they don't already exist
    if not page_logger.handlers:
        # Create log filename
        log_file = os.path.join(page_specific_log_dir, f"page_{page_num}.log")

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Create file handler for this page
        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)

        # Add handler to logger
        page_logger.addHandler(file_handler)
        page_logger.setLevel(logging.INFO)

        # Prevent propagation to root logger to avoid duplicate console output
        page_logger.propagate = False

    return page_logger


# Setup logging when module is imported
setup_logging()
