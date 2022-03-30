#!/usr/bin/env bash

TAG=$(date +%s)

docker build --tag "us-docker.pkg.dev/civic-eagle-enview-dev/civiceagle/github-stat-collector:$TAG" .
docker tag "us-docker.pkg.dev/civic-eagle-enview-dev/civiceagle/github-stat-collector:$TAG" us-docker.pkg.dev/civic-eagle-enview-dev/civiceagle/github-stat-collector:latest
docker push "us-docker.pkg.dev/civic-eagle-enview-dev/civiceagle/github-stat-collector:$TAG"
docker push us-docker.pkg.dev/civic-eagle-enview-dev/civiceagle/github-stat-collector:latest
