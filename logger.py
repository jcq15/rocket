import logging

log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

file_handler = logging.FileHandler('rocket.log', encoding='utf-8')
file_handler.setFormatter(log_formatter)

logger = logging.getLogger("rocket")
logger.setLevel(logging.INFO)
logger.addHandler(console_handler)
logger.addHandler(file_handler) 