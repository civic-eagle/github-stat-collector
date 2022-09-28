FROM python:slim

RUN apt-get update -qq \
  && apt-get install -yqq --no-install-recommends build-essential libgit2-dev \
  && pip3 install --disable-pip-version-check --no-cache-dir poetry crcmod

WORKDIR /app
COPY pyproject.toml .
COPY poetry.lock .
RUN poetry install --only main \
  && rm -r /root/.cache/pypoetry/cache /root/.cache/pypoetry/artifacts/

RUN apt-get remove -yqq build-essential \
  && apt-get autoremove -yqq \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

COPY github_stats/ github_stats/
COPY *.py /app/

ENTRYPOINT ["poetry", "run", "python"]
