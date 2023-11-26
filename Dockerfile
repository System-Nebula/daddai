FROM python:3.11.6-slim AS compile-image
RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential gcc
RUN useradd -rm -d /bot -s /bin/sh bot
USER bot
RUN ls -la /bot

RUN python -m venv /bot/venv
# Make sure we use the virtualenv:
ENV PATH="/bot/venv/bin:$PATH"

COPY deps/requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.11.6-slim AS build-image
RUN useradd -rm -d /bot -s /bin/sh bot
USER bot
COPY --chown=bot:root --from=compile-image /bot/venv /bot/venv
WORKDIR /bot
RUN mkdir /bot/.log
COPY --chown=bot:root . /bot
# Make sure we use the virtualenv:
ENV PATH="/bot/venv/bin:$PATH"
CMD ["python3", "/bot/main.py"]