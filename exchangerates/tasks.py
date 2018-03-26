import pendulum
import requests
from datetime import datetime
from xml.etree import ElementTree

from huey import crontab, RedisHuey

from models import ExchangeRate

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
            ExchangeRate.create(
                source='ecb',
                date=pendulum.parse(date.attrib['time'], strict=True),
                currency=currency.attrib['currency'],
                rate=currency.attrib['rate']
            )


if __name__ == '__main__':
    update_rates()
