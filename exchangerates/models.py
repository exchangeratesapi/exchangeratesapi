from walrus import Database, DateField, FloatField, Model, TextField, UUIDField

db = Database()


class ExchangeRate(Model):
    __database__ = db
    # id = TextField(primary_key=True)
    source = TextField(index=True)
    date = DateField(index=True)
    currency = TextField(index=True)
    rate = FloatField()
