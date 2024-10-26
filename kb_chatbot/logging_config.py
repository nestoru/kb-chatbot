# File: onenote_chatbot/logging_config.py

import logging

def configure_logging(default_level=logging.ERROR):
    """Configure logging for the application."""
    # Create a formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Create and configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(default_level)

    # Create console handler and set level to default
    console_handler = logging.StreamHandler()
    console_handler.setLevel(default_level)
    console_handler.setFormatter(formatter)

    # Add console handler to the root logger
    root_logger.addHandler(console_handler)

    # Configure specific loggers
    loggers_config = {
        'chromadb': logging.ERROR,
        'openai': logging.ERROR,
        # Add other packages/modules as needed
    }

    for logger_name, level in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)

    # Return the root logger in case it's needed elsewhere
    return root_logger
