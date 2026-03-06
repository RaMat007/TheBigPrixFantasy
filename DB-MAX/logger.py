import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "logs"
LOG_FILE = "app.log"

# Crear carpeta si no existe
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Configuración del logger
logger = logging.getLogger("quiniela_f1")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    f"{LOG_DIR}/{LOG_FILE}",
    maxBytes=500000,     # 500 KB antes de rotar
    backupCount=5        # mantiene 5 archivos anteriores
)

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

handler.setFormatter(formatter)
logger.addHandler(handler)

def get_logger():
    return logger

log = get_logger()
