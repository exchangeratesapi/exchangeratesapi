from exchangerates.models import db, ExchangeRates

with db:
  db.create_tables([ExchangeRates])
