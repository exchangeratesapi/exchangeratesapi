import itertools
import requests

from datetime import datetime
from decimal import Decimal
from xml.etree import ElementTree

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from gino.dialects.asyncpg import JSONB
from sanic import Sanic
from sanic.response import json

from exchangerates.utils import Gino

DB_HOST = 'localhost'
DB_DATABASE = 'exchangerates'

HISTORIC_RATES_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml'
LAST_90_DAYS_RATES_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml'

app = Sanic()
app.config.DB_HOST = DB_HOST
app.config.DB_DATABASE = DB_DATABASE
db = Gino()
db.init_app(app)


class ExchangeRates(db.Model):
    __tablename__ = 'exchange_rates'

    date = db.Column(db.Date(), primary_key=True)
    rates = db.Column(JSONB())

    def __repr__(self):
        return 'Rates [{}]'.format(self.date)


async def update_rates(historic=False):
    r = requests.get(HISTORIC_RATES_URL if historic else LAST_90_DAYS_RATES_URL)
    envelope = ElementTree.fromstring(r.content)

    namespaces = {
        'gesmes': 'http://www.gesmes.org/xml/2002-08-01',
        'eurofxref': 'http://www.ecb.int/vocabulary/2002-08-01/eurofxref'
    }

    data = envelope.findall('./eurofxref:Cube/eurofxref:Cube[@time]', namespaces)
    for d in data:
        time = datetime.strptime(d.attrib['time'], '%Y-%m-%d').date()
        rates = await ExchangeRates.get(time)
        if not rates:
            await ExchangeRates.create(
                date=time,
                rates={c.attrib['currency']: Decimal(c.attrib['rate']) for c in list(d)}
            )


@app.listener('before_server_start')
async def initialize_scheduler(app, loop):
    # Check that tables exist
    await db.gino.create_all()

    # Fill up database with rates
    # await update_rates(historic=True)

    # Schedule exchangerate updates
    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_rates, 'interval', hours=1)
    scheduler.start()


@app.route('/api/latest')
@app.route('/api/<date>')
async def exchange_rates(request, date=None):
    dt = datetime.now()
    if date:
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
        except ValueError as e:
            return json({'error': '{}'.format(e)}, status=400)

        if dt < datetime(1999, 1, 4):
            return json({'error': 'There is no data for dates older then 1999-01-04.'}, status=400)

    exchange_rates = await ExchangeRates.query.\
        where(ExchangeRates.date <= dt.date()). \
        order_by(ExchangeRates.date.desc()).\
        gino.first()
    rates = exchange_rates.rates

    # Base
    base = 'EUR'
    if 'base' in request.raw_args and request.raw_args['base'] != 'EUR':
        base = request.raw_args['base']

        if base in rates:
            rates = {currency: rate / rates[base] for currency, rate in rates.items()}
            rates['EUR'] = Decimal(1) / Decimal(rates[base])
        else:
            return json({'error': 'Base \'{}\' is not supported.'.format(base)}, status=400)

    # Symbols
    if 'symbols' in request.args:
        symbols = list(itertools.chain.from_iterable([symbol.split(',') for symbol in request.args['symbols']]))

        if all(symbol in rates for symbol in symbols):
            rates = {symbol: rates[symbol] for symbol in symbols}
        else:
            return json({
                'error': 'Symbols \'{}\' are invalid for date {}.'.format(','.join(symbols), dt.date())
            }, status=400)

    return json({
        'base': base,
        'date': exchange_rates.date.strftime('%Y-%m-%d'),
        'rates': rates
    })


# Static content
app.static('/static', './static')
app.static('/', './templates/index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, access_log=False, debug=False)