import ujson
import pendulum

import falcon
from peewee import fn
from exchangerates.models import db, ExchangeRates


class PeeweeConnectionMiddleware(object):
    def process_request(self, req, resp):
        db.connect()

    def process_response(self, req, resp, resource):
        if not db.is_closed():
           db.close()


class CORSMiddleware(object):
    def process_response(self, req, resp, resource, req_succeeded):
        resp.set_header('Access-Control-Allow-Origin', '*')

        if (req_succeeded
            and req.method == 'OPTIONS'
            and req.get_header('Access-Control-Request-Method')
        ):

            allow = resp.get_header('Allow')
            resp.delete_header('Allow')

            allow_headers = req.get_header(
                'Access-Control-Request-Headers',
                default='*'
            )

            resp.set_headers((
                ('Access-Control-Allow-Methods', allow),
                ('Access-Control-Allow-Headers', allow_headers),
                ('Access-Control-Max-Age', '86400'),  # 24 hours
            ))


class ExchangeRateResource(object):
    def on_get(self, request, response, date=None):
        if date:
            exchangerates = ExchangeRates.select().\
                where(ExchangeRates.date == date).\
                order_by(ExchangeRates.currency)
        else:
            ExchangeRatesAlias = ExchangeRates.alias()
            subquery = ExchangeRatesAlias.select(fn.MAX(ExchangeRatesAlias.date))
            exchangerates = ExchangeRates.select().\
                where(ExchangeRates.date == subquery).\
                order_by(ExchangeRates.currency)
        
        if 'symbols' in request.params:
            exchangerates = exchangerates.where(ExchangeRates.currency << request.params['symbols'])
        
        if 'base' in request.params:
            pass

        response.body = ujson.dumps({
            'base': 'EUR',
            'date': date,
            'rates': {er.currency:str(er.rate.normalize()) for er in exchangerates}
        })


exchangerates = ExchangeRateResource()

app = falcon.API(middleware=[
    PeeweeConnectionMiddleware(),
    CORSMiddleware(),
])
app.add_route('/latest/', exchangerates)
app.add_route('/{date}/', exchangerates)
