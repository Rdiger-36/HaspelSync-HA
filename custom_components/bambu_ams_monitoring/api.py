"""HTTP access to the backend outside the coordinator.

The coordinator owns the polling of a single printer. The printer list is read
somewhere else entirely: in both flows, which have no coordinator yet, and in
the ID repair at setup. That call carries the same API key and has to tell a
rejected key from an unreachable backend in all three places, so it lives here
once rather than three times.
"""

import aiohttp

from .const import REQUEST_TIMEOUT


class BackendUnauthorized(Exception):
    """The backend refused the API key, or none was sent."""


class BackendUnreachable(Exception):
    """The backend could not be reached, or answered something unusable."""


def auth_headers(api_key: str | None) -> dict:
    """The headers every request to the backend carries.

    The backend accepts the key as a bearer token or in X-API-Key and reads the
    bearer token first. An entry configured before the backend asked for a key
    holds none, and sending an empty header would be read as an empty key, so
    such a request goes out without one and is answered with 401.
    """
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


async def async_fetch_printers(session, base_url: str, api_key: str | None):
    """Reads the printer list of a backend.

    Raises BackendUnauthorized on 401 so a caller can ask for a key rather than
    claim the backend is down, and BackendUnreachable for everything else.

    @returns the list the backend answers with
    """
    url = f"{base_url.rstrip('/')}/api/printers"

    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        async with session.get(url, headers=auth_headers(api_key), timeout=timeout) as resp:
            if resp.status == 401:
                raise BackendUnauthorized(url)
            if resp.status != 200:
                raise BackendUnreachable(f"{url} answered HTTP {resp.status}")
            printers = await resp.json()
    except BackendUnauthorized:
        raise
    except (aiohttp.ClientError, ValueError, TimeoutError) as err:
        raise BackendUnreachable(f"{url} could not be read: {err}") from err

    if not isinstance(printers, list):
        raise BackendUnreachable(f"{url} answered something that is not a printer list")

    return printers
