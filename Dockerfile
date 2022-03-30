FROM python:3.10-slim

RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends ca-certificates build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --disable-pip-version-check --no-cache-dir -q poetry crcmod

WORKDIR /app
COPY pyproject.toml .
COPY poetry.lock .
RUN poetry install -q \
  && rm -r /root/.cache/pypoetry/cache /root/.cache/pypoetry/artifacts/

COPY github_stats/ github_stats/
COPY collect-stats.py .
# COPY config.yml .

CMD ["poetry", "run", "python", "/app/collect-stats.py"]
