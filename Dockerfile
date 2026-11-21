FROM node:22-bookworm-slim@sha256:de170b39439eb0e5a3444ad7d60b015614a381e10fecae2e30ec9e735122f38d AS makefun-cli

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /kit
ENTRYPOINT ["node", "/kit/cli/makefun.mjs"]

FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

ENV PYTHONHASHSEED=0
WORKDIR /bot
COPY main.py .
ENTRYPOINT ["python3", "-P", "-s", "/bot/main.py"]
