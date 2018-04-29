import ujson
import urllib.parse as urlparse

from gino.ext.sanic import Gino as GinoBase


class Gino(GinoBase):
    async def set_bind(self, bind, loop=None, **kwargs):
        kwargs.setdefault('strategy', 'sanic')
        return await super().set_bind(
            bind,
            loop=loop,
            json_serializer=ujson.dumps,
            json_deserializer=ujson.loads,
            **kwargs
        )


def parse_database_url(url):
    url = urlparse.urlparse(url)

    # Split query strings from path.
    path = url.path[1:]
    if '?' in path and not url.query:
        path, query = path.split('?', 2)
    else:
        path, query = path, url.query

    # Handle postgres percent-encoded paths.
    hostname = url.hostname or ''
    if '%2f' in hostname.lower():
        # Switch to url.netloc to avoid lower cased paths
        hostname = url.netloc
        if "@" in hostname:
            hostname = hostname.rsplit("@", 1)[1]
        if ":" in hostname:
            hostname = hostname.split(":", 1)[0]
        hostname = hostname.replace('%2f', '/').replace('%2F', '/')

    return {
        'DB_DATABASE': urlparse.unquote(path or ''),
        'DB_USER': urlparse.unquote(url.username or ''),
        'DB_PASSWORD': urlparse.unquote(url.password or ''),
        'DB_HOST': hostname,
        'DB_PORT': url.port
    }