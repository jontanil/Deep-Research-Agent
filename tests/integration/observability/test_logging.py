from conftest import LOGS_TEST_DIR
from src.observability.logging import logger


def test_logs_written_to_configured_dir():
    logger.error("synthetic log line")
    assert any(LOGS_TEST_DIR.glob("*.log"))