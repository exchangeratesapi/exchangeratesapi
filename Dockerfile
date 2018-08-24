FROM python:3.6.6-stretch

# install tool
RUN pip3 install pipenv
#RUN apk --update --no-cache add bash

WORKDIR /usr/src/app
COPY . .

CMD pipenv install --deploy --system && gunicorn exchangerates.app:app --bind 0.0.0.0:8000 --worker-class sanic.worker.GunicornWorker --max-requests 1000
