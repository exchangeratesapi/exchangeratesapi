import ujson

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