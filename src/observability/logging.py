import os
from loguru import logger
from datetime import datetime
from ..config.settings import get_settings

settings = get_settings()

now = datetime.now()
log_file_name = f'{settings.LOGS_DIR}/{now.strftime("%Y-%m-%d")}.log'

logger.add(log_file_name, rotation="00:00", level=settings.LOGGING_LEVEL)