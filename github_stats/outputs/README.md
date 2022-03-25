# General

We can extend the default `StatsOutput` object fairly simply. Because the default stat formatting simply creates a list of Influx-style JSON objects, re-formatting or outputting the data to any TSDB should be relatively painless.

# Outputs

## Google Cloud Monitoring (StackDriver)

A few small qualifiers for StackDriver:

1. StackDriver doesn't support negative numbers, we either have to pre-aggregate or drop any negative values.
2. StackDriver doesn't support backfilling data.

Knowing that, in order to ensure you can write data to StackDriver, you need to create a Google Application credentials. These can be either a local file or in memory, but need to be referenced by the GOOGLE_APPLICATION_CREDENTIALS environment variable. For example:

```bash
docker run --rm -v ~/google_grafana_auth.token:/tmp/gcreds -it -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcreds -e GITHUB_TOKEN=$GITHUB_TOKEN github-stats-collector:latest 
```
