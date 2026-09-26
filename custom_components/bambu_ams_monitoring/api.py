"""HTTP access to the backend outside the coordinator.

The coordinator owns the polling of a single printer. The printer list is read
somewhere else entirely: in both flows, which have no coordinator yet, and in
the ID repair at setup. That call carries the same API key and has to tell a
rejected key from an unreachable backend in all three places, so it lives here
once rather than three times. The actions the switch and the buttons send share
one call here for the same reason.
"""

import aiohttp

from .const import HTTP_HOST_REFUSED, REQUEST_TIMEOUT


class BackendUnauthorized(Exception):
    """The backend refused the API key, or none was sent."""


class BackendUnreachable(Exception):
    """The backend could not be reached, or answered something unusable."""


class BackendHostRefused(BackendUnreachable):
    """The backend refused the host name it was reached under.

    From 1.3.0 on the backend answers 403 to a request whose Host header is a
    name it does not know, which guards its Web UI against DNS rebinding. An IP
    address, localhost and a .local name always pass, anything else has to be
    listed under "Allowed host names" on its settings page. A subclass of
    BackendUnreachable, so a caller that does not tell the two apart still
    treats it as a backend it cannot use.
    """


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
    claim the backend is down, BackendHostRefused on 403 so it can name the
    setting that fixes it, and BackendUnreachable for everything else.

    @returns the list the backend answers with
    """
    url = f"{base_url.rstrip('/')}/api/printers"

    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        async with session.get(url, headers=auth_headers(api_key), timeout=timeout) as resp:
            if resp.status == 401:
                raise BackendUnauthorized(url)
            if resp.status == HTTP_HOST_REFUSED:
                raise BackendHostRefused(f"{url} refused the host name it was reached under")
            if resp.status != 200:
                raise BackendUnreachable(f"{url} answered HTTP {resp.status}")
            printers = await resp.json()
    except (BackendUnauthorized, BackendUnreachable):
        raise
    except (aiohttp.ClientError, ValueError, TimeoutError) as err:
        raise BackendUnreachable(f"{url} could not be read: {err}") from err

    if not isinstance(printers, list):
        raise BackendUnreachable(f"{url} answered something that is not a printer list")

    return printers


async def async_post_action(session, base_url: str, api_key: str | None, path: str):
    """Sends one of the backend actions and reads its answer.

    Every action endpoint answers a JSON body carrying `ok`, and some answer
    HTTP 200 with `ok: false` when there was nothing to do, so the caller gets
    both the status and the body to decide on. Nothing is raised for a status:
    a refused key is left to the next coordinator refresh, which turns it into
    the reauth flow for everybody rather than an error for whoever pressed.

    Raises BackendUnreachable when no answer arrived at all.

    @returns the HTTP status and the body, an empty dict when it was not JSON
    """
    url = f"{base_url.rstrip('/')}{path}"

    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        async with session.post(url, headers=auth_headers(api_key), timeout=timeout) as resp:
            try:
                body = await resp.json(content_type=None)
            except ValueError:
                body = None
            return resp.status, body if isinstance(body, dict) else {}
    except (aiohttp.ClientError, TimeoutError) as err:
        raise BackendUnreachable(f"{url} could not be reached: {err}") from err
