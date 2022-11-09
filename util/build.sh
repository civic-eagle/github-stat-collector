#!/usr/bin/env bash

# Only create deploy credentials if they exist
if [[ -n "${DEPLOY_KEY_FILE}" ]]; then
    echo "${DEPLOY_KEY_FILE}" > /tmp/credentials.json
    gcloud auth activate-service-account --key-file /tmp/credentials.json
    rm -f /tmp/credentials.json
fi

ROOT="gcr.io"
PROJECT="civic-eagle-enview-dev"
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
pushd "${SCRIPT_DIR}/../" >/dev/null 2>&1 || exit 1
TAG=${TAG:-$(git tag | tail -1)}

docker run --rm -v "${SCRIPT_DIR}/../:/apps" alpine/flake8:latest .
docker run --rm -v "${SCRIPT_DIR}/../:/data" cytopia/black:latest .

docker build --tag "${ROOT}/${PROJECT}/github-stat-collector:$TAG" .
docker tag "${ROOT}/${PROJECT}/github-stat-collector:$TAG" "${ROOT}/${PROJECT}/github-stat-collector:latest"
if [[ -n "${DEPLOY_KEY_FILE}" ]]; then
    docker --config /opt/docker-config/ push "${ROOT}/${PROJECT}/github-stat-collector:$TAG"
    docker --config /opt/docker-config/ push "${ROOT}/${PROJECT}/github-stat-collector:latest"
else
    docker push "${ROOT}/${PROJECT}/github-stat-collector:$TAG"
    docker push "${ROOT}/${PROJECT}/github-stat-collector:latest"
fi
