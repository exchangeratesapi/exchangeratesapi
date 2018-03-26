import ujson
import pendulum

import falcon
from exchangerates.models import db, ExchangeRates


class PeeweeConnectionMiddleware(object):
    def process_request(self, req, resp):
        db.connect()

    def process_response(self, req, resp, resource):
        if not db.is_closed():
           db.close()


class ExchangeRateResource(object):
    def on_get(self, request, response, date=None):
        if date:
            exchangerates = ExchangeRates.select().where(ExchangeRates.date == date)

        response.body = ujson.dumps({
            'base': 'EUR',
            'date': date,
            'rates': {er.currency:str(er.rate) for er in exchangerates}
        })


exchangerates = ExchangeRateResource()

app = falcon.API(middleware=[
    PeeweeConnectionMiddleware()
])
app.add_route('/latest/', exchangerates)
app.add_route('/{date}/', exchangerates)
