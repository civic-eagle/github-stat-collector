# can't use alpine image until libgit2 >= 1.4
FROM python:3-slim

RUN apt-get update -qq \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends ca-certificates build-essential \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  && pip3 install --disable-pip-version-check --no-cache-dir poetry crcmod

WORKDIR /app
COPY pyproject.toml .
COPY poetry.lock .
RUN poetry install --no-dev \
  && rm -r /root/.cache/pypoetry/cache /root/.cache/pypoetry/artifacts/

RUN apt-get remove -y -qq build-essential gcc-9-base \
  && apt-get autoremove -y -qq \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

COPY github_stats/ github_stats/
COPY collect-stats.py .

ENTRYPOINT ["poetry", "run", "python", "/app/collect-stats.py", "-c", "/app/config.yml"]
