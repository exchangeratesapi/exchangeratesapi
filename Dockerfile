FROM python:3.6.6-stretch

# install tools
RUN pip3 install pipenv

WORKDIR /usr/src/app
COPY . .

CMD pipenv install --deploy --system && gunicorn exchangerates.app:app --bind 0.0.0.0:8000 --worker-class sanic.worker.GunicornWorker --max-requests 1000
