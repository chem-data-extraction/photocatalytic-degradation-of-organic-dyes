import os
import sys
import logging

# ANSI escape codes for colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Define a custom SUCCESS level (between INFO/20 and WARNING/30)
SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")

def success(self, message, *args, **kws):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kws)

logging.Logger.success = success

def plain(self, message, *args, **kws):
    """Log a message without any level prefix or decoration."""
    extra = kws.setdefault('extra', {})
    extra['plain'] = True
    if self.isEnabledFor(logging.INFO):
        self._log(logging.INFO, message, args, **kws)

logging.Logger.plain = plain

class ConsoleFormatter(logging.Formatter):
    """Custom formatter for console output.
    Precludes timestamp to keep console clean, highlights log level with colors,
    and preserves message indentation by placing the log level prefix after the indent.
    """
    def format(self, record):
        orig_msg = record.msg
        orig_args = record.args
        
        msg = record.getMessage()
        l_spaces = len(msg) - len(msg.lstrip())
        indent = msg[:l_spaces]
        
        # Temporarily modify record message to place prefix after indentation
        record.msg = msg.lstrip()
        record.args = ()
        
        is_tty = sys.stdout.isatty()
        level = record.levelno
        
        if getattr(record, 'plain', False):
            result = f"{indent}{record.msg}"
        else:
            if is_tty:
                if level >= logging.ERROR:
                    prefix = f"{RED}{BOLD}[ERROR]{RESET} "
                elif level >= logging.WARNING:
                    prefix = f"{YELLOW}{BOLD}[WARNING]{RESET} "
                elif level == SUCCESS_LEVEL_NUM:
                    prefix = f"{GREEN}{BOLD}[SUCCESS]{RESET} "
                elif level >= logging.INFO:
                    prefix = f"{CYAN}[INFO]{RESET} "
                else:
                    prefix = f"{RESET}[DEBUG] "
            else:
                if level >= logging.ERROR:
                    prefix = "[ERROR] "
                elif level >= logging.WARNING:
                    prefix = "[WARNING] "
                elif level == SUCCESS_LEVEL_NUM:
                    prefix = "[SUCCESS] "
                elif level >= logging.INFO:
                    prefix = "[INFO] "
                else:
                    prefix = "[DEBUG] "
                    
            formatted = super().format(record)
            result = f"{indent}{prefix}{formatted}"
            
        record.msg = orig_msg
        record.args = orig_args
        return result

class FileFormatter(logging.Formatter):
    """Custom formatter for file output.
    Includes timestamps and puts the log level prefix after the indent.
    """
    def __init__(self, fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"):
        super().__init__(fmt, datefmt)
        
    def format(self, record):
        orig_msg = record.msg
        orig_args = record.args
        
        msg = record.getMessage()
        l_spaces = len(msg) - len(msg.lstrip())
        indent = msg[:l_spaces]
        
        record.msg = msg.lstrip()
        record.args = ()
        
        if getattr(record, 'plain', False):
            asctime = self.formatTime(record, self.datefmt)
            result = f"{asctime} [PLAIN] {indent}{record.msg}"
        else:
            formatted = super().format(record)
            result = f"{indent}{formatted}"
            
        record.msg = orig_msg
        record.args = orig_args
        return result

def get_logger(name: str, log_file: str = None) -> logging.Logger:
    """Get a configured logger instance.
    
    Args:
        name: Name of the logger.
        log_file: Path to a log file to write logs to. If None, only console logging is used.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers if logger was already initialized
    if logger.handlers:
        return logger
        
    # Console Handler (writes to stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(console_handler)
    
    # Override log directory if running under pipeline
    pipeline_log_dir = os.environ.get("PIPELINE_LOG_DIR")
    if pipeline_log_dir:
        actual_log_name = os.path.basename(log_file) if log_file else f"{name}.log"
        log_file = os.path.join(pipeline_log_dir, actual_log_name)
    elif log_file:
        # Default to logs directory for relative log file paths
        if not os.path.isabs(log_file):
            parts = log_file.split(os.sep)
            if parts[0] != "logs":
                log_file = os.path.join("logs", log_file)
    
    # File Handler
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(FileFormatter())
        logger.addHandler(file_handler)
        
    return logger
