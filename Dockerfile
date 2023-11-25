FROM python:3.7-slim AS compile-image
RUN apt update && apt install -y --no-install-recommends build-essential gcc
COPY deps/requirements.txt .
RUN pip install --user -r requirements.txt
FROM python:3.7-slim AS build-image
COPY --from=compile-image /root/.local /root/.local
ENV PATH=/root/.local/:$PATH
RUN mkdir /bot
RUN mkdir /bot/.log
WORKDIR /bot
COPY . .
CMD ["/bin/python3", "main.py"]