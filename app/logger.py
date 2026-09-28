import logging
import sys


# =========================
# 日志格式
# =========================

LOG_FORMAT = (
    "%(asctime)s | "
    "%(levelname)s | "
    "%(name)s | "
    "%(message)s"
)


# =========================
# 配置日志
# =========================

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)


# =========================
# 获取项目日志器
# =========================

logger = logging.getLogger("ai-knowledge-system")