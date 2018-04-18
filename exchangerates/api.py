from __future__ import division

import datetime
from decimal import ROUND_HALF_UP, Decimal

import falcon
import ujson
from peewee import fn

from exchangerates.models import ExchangeRates, db


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
        # Check that date is in range
        if date and date < datetime.datetime(1999, 1, 4):
            raise falcon.HTTPBadRequest('There is no data for dates older then 1999-01-04.')

        # If latest
        if not date:
            date = datetime.date.today()

        subquery = ExchangeRates.filter(ExchangeRates.date <= date).\
            select(fn.MAX(ExchangeRates.date))

        exchangerates = ExchangeRates.\
            select(ExchangeRates.currency, ExchangeRates.rate, ExchangeRates.date).\
            filter(ExchangeRates.date == subquery).\
            order_by(ExchangeRates.currency)

        # Symbols
        if 'symbols' in request.params:
            exchangerates = exchangerates.\
                where(ExchangeRates.currency << request.params['symbols'])
        
        # Convert to dictionaries
        exchangerates = exchangerates.dicts()
        rates = {er['currency']:er['rate'] for er in exchangerates}
        
        # Base
        base = request.params['base'] if 'base' in request.params else 'EUR'
        if base != 'EUR':
            if base in rates:
                base_rate = (Decimal(1) / rates[base]).quantize(Decimal('0.0001'), ROUND_HALF_UP)
                # TODO: For better performance this can probably be done within Postgres already
                rates = {currency:(rate / rates[base]).quantize(Decimal('0.0001'), ROUND_HALF_UP) for currency, rate in rates.iteritems()}
                rates['EUR'] = base_rate
                del rates[base]
            else:
                raise falcon.HTTPBadRequest('Currency code {} is not supported.')

        response.body = ujson.dumps({
            'base': base,
            'date': exchangerates[0]['date'].strftime('%Y-%m-%d'),
            'rates': rates
        })


exchangerates = ExchangeRateResource()

app = falcon.API(middleware=[
    PeeweeConnectionMiddleware(),
    CORSMiddleware(),
])
app.add_route('/api/latest/', exchangerates)
app.add_route('/api/{date:dt("%Y-%m-%d")}/', exchangerates)
