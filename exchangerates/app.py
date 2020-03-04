import fcntl
import itertools
import requests

from datetime import datetime
from decimal import Decimal
from os import getenv
from xml.etree import ElementTree

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from gino.dialects.asyncpg import JSONB
from raven.contrib.sanic import Sentry
from sanic import Sanic
from sanic.response import file, html, json, redirect

from exchangerates.utils import Gino, cors, parse_database_url

HISTORIC_RATES_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
LAST_90_DAYS_RATES_URL = (
    "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
)


app = Sanic()
app.config.update(
    parse_database_url(
        url=getenv("DATABASE_URL", "postgresql://localhost/exchangerates")
    )
)

# Database
db = Gino(app)

# Sentry
sentry = Sentry(app)


class ExchangeRates(db.Model):
    __tablename__ = "exchange_rates"

    date = db.Column(db.Date(), primary_key=True)
    rates = db.Column(JSONB())

    def __repr__(self):
        return "Rates [{}]".format(self.date)


async def update_rates(historic=False):
    r = requests.get(HISTORIC_RATES_URL if historic else LAST_90_DAYS_RATES_URL)
    envelope = ElementTree.fromstring(r.content)

    namespaces = {
        "gesmes": "http://www.gesmes.org/xml/2002-08-01",
        "eurofxref": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref",
    }

    data = envelope.findall("./eurofxref:Cube/eurofxref:Cube[@time]", namespaces)
    for d in data:
        time = datetime.strptime(d.attrib["time"], "%Y-%m-%d").date()
        rates = await ExchangeRates.get(time)
        if not rates:
            await ExchangeRates.create(
                date=time,
                rates={
                    c.attrib["currency"]: Decimal(c.attrib["rate"]) for c in list(d)
                },
            )


@app.listener("before_server_start")
async def initialize_scheduler(app, loop):
    # Check that tables exist
    await db.gino.create_all()

    # Schedule exchangerate updates
    try:
        _ = open("scheduler.lock", "w")
        fcntl.lockf(_.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        scheduler = AsyncIOScheduler()
        scheduler.start()

        # Updates lates 90 days data
        scheduler.add_job(update_rates, "interval", hours=1)

        # Fill up database with rates
        count = await db.func.count(ExchangeRates.date).gino.scalar()
        scheduler.add_job(update_rates, kwargs={"historic": True})
    except BlockingIOError:
        pass


@app.middleware("request")
async def force_ssl(request):
    if request.headers.get("X-Forwarded-Proto") == "http":
        return redirect(request.url.replace("http://", "https://", 1), status=301)


@app.middleware("request")
async def force_naked_domain(request):
    if request.host.startswith("www."):
        return redirect(request.url.replace("www.", "", 1), status=301)


@app.route("/latest", methods=["GET", "HEAD"])
@app.route("/<date>", methods=["GET", "HEAD"])
@app.route("/api/latest", methods=["GET", "HEAD"])
@app.route("/api/<date>", methods=["GET", "HEAD"])
@cors()
async def exchange_rates(request, date=None):
    if request.method == "HEAD":
        return json("")

    dt = datetime.now()
    if date:
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
        except ValueError as e:
            return json({"error": "{}".format(e)}, status=400)

        if dt < datetime(1999, 1, 4):
            return json(
                {"error": "There is no data for dates older then 1999-01-04."},
                status=400,
            )

    exchange_rates = (
        await ExchangeRates.query.where(ExchangeRates.date <= dt.date())
        .order_by(ExchangeRates.date.desc())
        .gino.first()
    )
    rates = exchange_rates.rates

    # Base
    base = "EUR"
    if "base" in request.raw_args and request.raw_args["base"] != "EUR":
        base = request.raw_args["base"]

        if base in rates:
            base_rate = Decimal(rates[base])
            rates = {
                currency: Decimal(rate) / base_rate for currency, rate in rates.items()
            }
            rates["EUR"] = Decimal(1) / base_rate
        else:
            return json(
                {"error": "Base '{}' is not supported.".format(base)}, status=400
            )

    else:
        rates["EUR"] = Decimal(1)

    # Symbols
    if "symbols" in request.args:
        symbols = list(
            itertools.chain.from_iterable(
                [symbol.split(",") for symbol in request.args["symbols"]]
            )
        )

        if all(symbol in rates for symbol in symbols):
            rates = {symbol: rates[symbol] for symbol in symbols}
        else:
            return json(
                {
                    "error": "Symbols '{}' are invalid for date {}.".format(
                        ",".join(symbols), dt.date()
                    )
                },
                status=400,
            )

    return json(
        {"base": base, "date": exchange_rates.date.strftime("%Y-%m-%d"), "rates": rates}
    )


@app.route("/history", methods=["GET", "HEAD"])
@app.route("/api/history", methods=["GET", "HEAD"])
@cors()
async def exchange_rates(request):
    if request.method == "HEAD":
        return json("")

    if "start_at" in request.raw_args:
        try:
            start_at = datetime.strptime(request.raw_args["start_at"], "%Y-%m-%d")
        except ValueError as e:
            return json(
                {"error": "start_at parameter format", "exception": "{}".format(e)},
                status=400,
            )
    else:
        return json({"error": "missing start_at parameter"})

    if "end_at" in request.raw_args:
        try:
            end_at = datetime.strptime(request.raw_args["end_at"], "%Y-%m-%d")
        except ValueError as e:
            return json(
                {"error": "end_at parameter format", "exception": "{}".format(e)},
                status=400,
            )
    else:
        return json({"error": "missing end_at parameter"})

    exchange_rates = (
        await ExchangeRates.query.where(ExchangeRates.date >= start_at.date())
        .where(ExchangeRates.date <= end_at.date())
        .order_by(ExchangeRates.date.asc())
        .gino.all()
    )

    base = "EUR"
    historic_rates = {}
    for er in exchange_rates:
        rates = er.rates

        if "base" in request.raw_args and request.raw_args["base"] != "EUR":
            base = request.raw_args["base"]

            if base in rates:
                base_rate = Decimal(rates[base])
                rates = {
                    currency: Decimal(rate) / base_rate
                    for currency, rate in rates.items()
                }
                rates["EUR"] = Decimal(1) / base_rate
            else:
                return json(
                    {"error": "Base '{}' is not supported.".format(base)}, status=400
                )

        else:
            rates["EUR"] = Decimal(1)

        # Symbols
        if "symbols" in request.args:
            symbols = list(
                itertools.chain.from_iterable(
                    [symbol.split(",") for symbol in request.args["symbols"]]
                )
            )

            if all(symbol in rates for symbol in symbols):
                rates = {symbol: rates[symbol] for symbol in symbols}
            else:
                return json(
                    {"error": "Symbols '{}' are invalid.".format(",".join(symbols))},
                    status=400,
                )

        historic_rates[er.date] = rates

    return json({"base": base, "start_at": start_at.date().isoformat(), "end_at": end_at.date().isoformat(), "rates": historic_rates})


# api.ExchangeratesAPI.io
@app.route("/", methods=["GET"], host="api.exchangeratesapi.io")
async def index(request):
    return json({"details": "https://exchangeratesapi.io"}, escape_forward_slashes=False)


# Website
@app.route("/", methods=["GET", "HEAD"])
async def index(request):
    if request.method == "HEAD":
        return html("")
    return await file("./exchangerates/templates/index.html")


# Static content
app.static("/static", "./exchangerates/static")
app.static("/robots.txt", "./exchangerates/static/robots.txt")
app.static("/favicon.ico", "./exchangerates/static/favicon.ico")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, access_log=False, debug=True)
