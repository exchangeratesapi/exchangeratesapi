from exchangerates.models import db, ExchangeRate

with db:
  db.create_tables([ExchangeRate])
