"""
Centralized logging configuration
"""
import logging
import logging.handlers
from config import LOG_LEVEL, LOG_FORMAT, LOGS_DIR
from pathlib import Path

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)

def setup_logger(name: str, log_file: str = None) -> logging.Logger:
    """
    Setup a logger with both file and console handlers.
    
    Args:
        name: Logger name (usually __name__)
        log_file: Log file name (optional)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))

    # Avoid duplicate handlers during Streamlit reruns/re-imports.
    if logger.handlers:
        return logger
    
    # Formatter
    formatter = logging.Formatter(LOG_FORMAT)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if log_file specified)
    if log_file:
        log_path = LOGS_DIR / log_file
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10485760,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, LOG_LEVEL))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Create module-level loggers
scanner_logger = setup_logger("scanner", "scanner.log")
lead_scorer_logger = setup_logger("lead_scorer", "lead_scorer.log")
comment_worker_logger = setup_logger("comment_worker", "comment_worker.log")
app_logger = setup_logger("app", "app.log")
database_logger = setup_logger("database", "database.log")
