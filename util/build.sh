#!/usr/bin/env bash

ROOT="gcr.io"
PROJECT="civic-eagle-enview-dev"
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
pushd "${SCRIPT_DIR}/../" >/dev/null 2>&1 || exit 1
TAG=${TAG:-$(git tag | tail -1)}

docker run --rm -v "${SCRIPT_DIR}/../:/apps" alpine/flake8:latest .
docker run --rm -v "${SCRIPT_DIR}/../:/data" cytopia/black:latest .

docker build --tag "${ROOT}/${PROJECT}/github-stat-collector:$TAG" .
docker tag "${ROOT}/${PROJECT}/github-stat-collector:$TAG" "${ROOT}/${PROJECT}/github-stat-collector:latest"
docker push "${ROOT}/${PROJECT}/github-stat-collector:$TAG"
docker push "${ROOT}/${PROJECT}/github-stat-collector:latest"
