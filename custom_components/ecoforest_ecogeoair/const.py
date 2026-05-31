from datetime import timedelta

import aiohttp

DOMAIN = "ecoforest_ecogeoair"
MANUFACTURER = "Ecoforest"

# Default Easynet API timeout - tolerate slow response
LOCAL_TIMEOUT = aiohttp.ClientTimeout(sock_connect=10.0, total=60.0)

# Polling periodicity - 1 minute default; sometimes needs a gap between data reads
POLLING_INTERVAL = timedelta(seconds=60)

# Service enable flags (2104/2108/2116/2113) change rarely; machine uses 2148 ico1
SERVICE_ENABLE_POLLING_INTERVAL = timedelta(minutes=15)
