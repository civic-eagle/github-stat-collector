#!/usr/bin/env bash

TAG=${TAG:-$(date +%s)}
ROOT="gcr.io"
PROJECT="civic-eagle-enview-dev"

docker build --tag "${ROOT}/${PROJECT}/github-stat-collector:$TAG" .
docker tag "${ROOT}/${PROJECT}/github-stat-collector:$TAG" "${ROOT}/${PROJECT}/github-stat-collector:latest"
docker push "${ROOT}/${PROJECT}/github-stat-collector:$TAG"
docker push "${ROOT}/${PROJECT}/github-stat-collector:latest"
