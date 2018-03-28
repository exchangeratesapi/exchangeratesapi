from datetime import datetime
from decimal import Decimal
from xml.etree import ElementTree

import requests
from huey import RedisHuey, crontab

from models import ExchangeRates

huey = RedisHuey()


HISTORY_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml'
LAST_90_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml'


@huey.periodic_task(crontab(minute='5', hour='*'))
def update_rates(history=False):
    r = requests.get(HISTORY_URL if history else LAST_90_URL)
    envelope = ElementTree.fromstring(r.content)

    namespaces = {
        'gesmes': 'http://www.gesmes.org/xml/2002-08-01',
        'eurofxref': 'http://www.ecb.int/vocabulary/2002-08-01/eurofxref'
    }

    dates = envelope.findall('./eurofxref:Cube/eurofxref:Cube[@time]', namespaces)
    for date in dates:

        for currency in list(date):
            ExchangeRates.get_or_create(
                source='ecb',
                date=date.attrib['time'],
                currency=currency.attrib['currency'],
                defaults={
                    'rate': Decimal(currency.attrib['rate'])
                }
            )
