# utils/logger.py
"""
Centralized logging configuration for the DEX sniping system.
Provides structured logging with different levels and formatters.
"""

import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

class LoggerManager:
    """Manages logging configuration for different components."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self._ensure_log_directory()
        self._setup_root_logger()
        
    def _ensure_log_directory(self) -> None:
        """Create log directory if it doesn't exist."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
    def _setup_root_logger(self) -> None:
        """Configure the root logger with handlers - Windows Unicode compatible."""
        import sys
        
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        root_logger.handlers.clear()
        
        # Console handler with colors and Unicode support
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Set encoding for Windows compatibility
        if hasattr(console_handler.stream, 'reconfigure'):
            try:
                console_handler.stream.reconfigure(encoding='utf-8')
            except:
                pass  # Fallback if reconfigure fails
        
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler for all logs with UTF-8 encoding
        file_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(self.log_dir, 'dex_sniping.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'  # Explicit UTF-8 encoding
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Error file handler with UTF-8 encoding
        error_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(self.log_dir, 'errors.log'),
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding='utf-8'  # Explicit UTF-8 encoding
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)






    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance for a specific component."""
        return logging.getLogger(name)
        
    def create_component_logger(self, component_name: str) -> logging.Logger:
        """Create a specialized logger for a component with its own file."""
        logger = logging.getLogger(component_name)
        
        # Component-specific file handler
        component_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(self.log_dir, f'{component_name.lower()}.log'),
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        component_handler.setLevel(logging.DEBUG)
        component_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        component_handler.setFormatter(component_formatter)
        logger.addHandler(component_handler)
        
        return logger

# Initialize global logger manager
logger_manager = LoggerManager()
