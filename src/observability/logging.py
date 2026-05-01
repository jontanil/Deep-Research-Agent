import os
from loguru import logger
from datetime import datetime
from ..config.settings import get_settings

now = datetime.now()
log_file_name = f'logs/{now.strftime("%Y-%m-%d")}.log'

settings = get_settings()

logger.add(log_file_name, rotation="00:00", level=settings.LOGGING_LEVEL)