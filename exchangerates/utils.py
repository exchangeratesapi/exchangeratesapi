import ujson
import urllib.parse as urlparse

from functools import wraps
from inspect import isawaitable

from gino.ext.sanic import Gino as GinoBase
from sanic.response import BaseHTTPResponse


class Gino(GinoBase):
    async def set_bind(self, bind, loop=None, **kwargs):
        kwargs.setdefault("strategy", "sanic")
        return await super().set_bind(
            bind,
            loop=loop,
            json_serializer=ujson.dumps,
            json_deserializer=ujson.loads,
            **kwargs
        )


def cors(origin=None):
    CORS_HEADERS = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
    }

    def decorator(fn):
        @wraps(fn)
        def wrap(*args, **kwargs):
            response = fn(*args, **kwargs)
            if isinstance(response, BaseHTTPResponse):
                response.headers.update(CORS_HEADERS)
                return response
            elif isawaitable(response):

                async def make_cors():
                    r = await response
                    r.headers.update(CORS_HEADERS)
                    return r

                return make_cors()
            return response

        return wrap

    return decorator


def parse_database_url(url):
    url = urlparse.urlparse(url)

    # Split query strings from path.
    path = url.path[1:]
    if "?" in path and not url.query:
        path, query = path.split("?", 2)
    else:
        path, query = path, url.query

    # Handle postgres percent-encoded paths.
    hostname = url.hostname or ""
    if "%2f" in hostname.lower():
        # Switch to url.netloc to avoid lower cased paths
        hostname = url.netloc
        if "@" in hostname:
            hostname = hostname.rsplit("@", 1)[1]
        if ":" in hostname:
            hostname = hostname.split(":", 1)[0]
        hostname = hostname.replace("%2f", "/").replace("%2F", "/")

    config = {
        "DB_DATABASE": urlparse.unquote(path) if path else None,
        "DB_USER": urlparse.unquote(url.username) if url.username else None,
        "DB_PASSWORD": urlparse.unquote(url.password) if url.password else None,
        "DB_HOST": hostname,
        "DB_PORT": url.port,
    }
    return {k: v for k, v in config.items() if v is not None}
