from peewee import (
    SqliteDatabase, Model, CharField, CompositeKey, DateField, DecimalField
)

db = SqliteDatabase('exchangerates.db')


class ExchangeRate(Model):
    source = CharField(choices=(('ecb', 'European Central Bank'),))
    date = DateField(index=True)
    currency = CharField()
    rate = DecimalField()

    class Meta:
        database = db
        primary_key = CompositeKey('date', 'currency')
