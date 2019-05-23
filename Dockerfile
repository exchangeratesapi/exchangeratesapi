ARG TARGET_ENV=production
FROM python:3.6-slim AS base
RUN apt-get update \
    && apt-get install -y gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pipenv

ENV APP_HOME=/usr/src/app
RUN mkdir -p $APP_HOME
WORKDIR $APP_HOME

COPY Pipfile* /usr/src/app/
RUN pipenv install --system --deploy
ENTRYPOINT ["gunicorn", "exchangerates.app:app", "-b", "0.0.0.0:8000", "--worker-class", "sanic.worker.GunicornWorker"]

FROM base AS build-development
#Mount local dev files to app home.
VOLUME [ "$APP_HOME" ]
#We cannot write into the volume since it (could/should) be readonly, we'll write outside the volume
ENV SCHEDULER_LOCKFILE=/usr/src/scheduler.lock
CMD ["--reload"]

FROM base AS build-production
COPY . /usr/src/app
CMD ["--max-requests", "1000"]

FROM build-$TARGET_ENV
EXPOSE 8000