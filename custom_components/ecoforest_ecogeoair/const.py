from datetime import timedelta

import aiohttp

DOMAIN = "ecoforest_ecogeoair"
MANUFACTURER = "Ecoforest"

# Default Easynet API timeout - tolerate slow response
LOCAL_TIMEOUT = aiohttp.ClientTimeout(sock_connect=10.0, total=60.0)

# Polling periodicity - 1 minute default; sometimes needs a gap between data reads
POLLING_INTERVAL = timedelta(seconds=60)
