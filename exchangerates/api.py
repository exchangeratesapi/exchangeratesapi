import json
import pendulum

import falcon

from models import ExchangeRate


class ExchangeRateResource(object):
    def on_get(self, request, response, date=None):
        if date:
            exchangerates = ExchangeRate.query(
                ExchangeRate.date == pendulum.parse(date, strict=True)
            )

        response.body = json.dumps({
            'base': 'EUR',
            'date': date,
            'rates': {er.currency:er.rate for er in exchangerates}
        })


exchangerates = ExchangeRateResource()

app = falcon.API()
app.add_route('/latest/', exchangerates)
app.add_route('/{date}/', exchangerates)
