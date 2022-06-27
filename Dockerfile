FROM python:alpine

RUN apk add --no-cache libffi libffi-dev musl-dev g++ libgit2-dev \
  && pip3 install --disable-pip-version-check --no-cache-dir poetry crcmod

WORKDIR /app
COPY pyproject.toml .
COPY poetry.lock .
RUN poetry install --no-dev \
  && rm -r /root/.cache/pypoetry/cache /root/.cache/pypoetry/artifacts/

RUN apk del g++ musl-dev libffi-dev

COPY github_stats/ github_stats/
COPY collect-stats.py .

ENTRYPOINT ["poetry", "run", "python"]
