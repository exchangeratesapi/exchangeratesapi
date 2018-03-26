# import pendulum
import requests

from datetime import datetime
from decimal import Decimal
from huey import crontab, RedisHuey
from models import ExchangeRate
from xml.etree import ElementTree

huey = RedisHuey()


# @huey.periodic_task(crontab(minute='*'))
@huey.task()
def update_rates():
    r = requests.get('https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml')
    envelope = ElementTree.fromstring(r.content)

    namespaces = {
        'gesmes': 'http://www.gesmes.org/xml/2002-08-01',
        'eurofxref': 'http://www.ecb.int/vocabulary/2002-08-01/eurofxref'
    }

    dates = envelope.findall('./eurofxref:Cube/eurofxref:Cube[@time]', namespaces)
    for date in dates:

        for currency in list(date):
            er = ExchangeRate.get_or_create(
                source='ecb',
                date=date.attrib['time'],
                currency=currency.attrib['currency'],
                rate=Decimal(currency.attrib['rate'])
            )
            print(er)


if __name__ == '__main__':
    update_rates()
