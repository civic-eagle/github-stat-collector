#!/usr/bin/env bash

TAG=$(date +%s)
ROOT="us-central1-docker.pkg.dev"
PROJECT="civic-eagle-enview-dev"
REPO="docker"

docker build --tag "${ROOT}/${PROJECT}/${REPO}/github-stat-collector:$TAG" .
docker tag "${ROOT}/${PROJECT}/${REPO}/github-stat-collector:$TAG" us-docker.pkg.dev/civic-eagle-enview-dev/civiceagle/github-stat-collector:latest
docker push "${ROOT}/${PROJECT}/${REPO}/github-stat-collector:$TAG"
docker push "${ROOT}/${PROJECT}/${REPO}/github-stat-collector:latest"
