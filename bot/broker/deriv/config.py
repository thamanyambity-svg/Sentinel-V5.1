"""
Configuration Deriv – Go 4.7
"""

import os
DERIV_API_MODE = os.getenv("DERIV_API_MODE", "REAL")  # DISABLED | DRY_RUN | REAL
