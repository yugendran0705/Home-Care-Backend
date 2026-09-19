# /utils/logger.py

import logging

# Single application-wide logger. Handlers, level, and format are configured
# once at startup (see main.py); every module imports this instance and logs
# through it rather than creating its own. Standalone processes that don't boot
# through main.py (e.g. workers) configure logging themselves before using it.
logger = logging.getLogger("homecare")
