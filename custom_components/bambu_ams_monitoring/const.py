from datetime import timedelta

DOMAIN = "bambu_ams_monitoring"

CONF_BASE_URL = "base_url"
CONF_PRINTERS = "printers"

CONF_ERR_CANNOT_CONNECT = "cannot_connect"

# The switch was the only platform for a long time. It stays first in the list
# so an existing installation keeps the order it already shows.
PLATFORMS = ["switch", "sensor", "binary_sensor"]

# Where the per printer coordinators live inside hass.data[DOMAIN][entry_id].
DATA_COORDINATORS = "coordinators"

# The backend pushes AMS environment readings to its own dashboard at most every
# 30 seconds, and an AMS update runs on the printer update interval, which is
# longer still. Polling faster than that only produces identical answers.
UPDATE_INTERVAL = timedelta(seconds=30)

# /api/print may fetch the sliced file over FTPS when the printer reports a job
# the backend has not cached yet, which is the one call here that can be slow.
REQUEST_TIMEOUT = 30

# The action the backend offers for a slot, as the literal strings SLOT_OPTIONS
# in the backend defines. These three mean there is nothing for the user to do,
# everything else is work waiting in the Web UI. Compared as text because the
# backend sends the label rather than a key.
SLOT_OPTIONS_WITHOUT_WORK = {
    "No actions available",
    "Waiting for data",
    "Show Info!",
}

# The slot label the backend gives the external spool holder. It is not part of
# any AMS unit, so it never carries environment readings.
EXTERNAL_SLOT = "External"
