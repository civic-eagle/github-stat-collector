[![CI](https://github.com/civic-eagle/github-stat-collector/actions/workflows/ci.yaml/badge.svg)](https://github.com/civic-eagle/github-stat-collector/actions/workflows/ci.yaml)
[![scheduled stat collection](https://github.com/civic-eagle/github-stat-collector/actions/workflows/run.yml/badge.svg)](https://github.com/civic-eagle/github-stat-collector/actions/workflows/run.yml)

# Installing

This tool relies on `poetry` for dependency management. If you already have `poetry` installed on your system, simply `poetry update` to pull in all needed dependencies.

## Google/Stackdriver Output

Leveraging the Google output requires `poetry add opencensus opencensus-ext-stackdriver`. We normally keep these dependencies out of the program to significantly reduce install size and build time. You _will_ have problems with this output as Stackdriver doesn't allow negative numbers in custom metrics.

# Github Auth Token

Github doesn't support organization-level auth tokens (yet), so a user must make a personal auth token to get permissions for this tool to work. The [upstream docs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) describe the basic pattern, but we need the following permissions on the token for it to work:

- `admin:org`
- `admin:repo_hook`
- `delete:packages`
- `notifications`
- `repo`
- `workflow`
- `write:packages`

# Configuration

[Example configuration](config.exmaple.yml)

Configuration largely defines the repos (and any custom work to do in the repo) and the output location.

_ssh urls (e.g. git@github.com:civic-eagle/github-stats-collector.git) for Github repos has not been tested in this tool and likely won't work._

# Backfilling Data

We can leverage the `backfill-stats.py` script to loop over longer time ranges and fill in data:

```bash
/app/backfill-stats.py -c /app/config.yml --start-timestamp 1650283200 --stop-timestamp 1652835600 --timestamp-step 3600 --sleep-time 1800
```

Example above would collect data between Mon Apr 18 12:00:00 UTC 2022 and Wednesday, May 18, 2022 1:00:00 AM at one hour intervals. Or put another way, it would perform 720 individual runs of the application.

# Metrics formatting

We'll adhere to the OpenMetrics standard as much as possible:

https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md

# Label matching

Because we may want additional or aggregate labels for tracking work in the repository, we can create these matching groups in our config. Any custom labels added will override the default labels collected.

# Notes on user name formatting

Because Github API endpoints don't return consistent user names between each of them, we may see _some_ overlap of users, but we attempt to get user names as close to consistent (one mapping per user) as possible.

The most frequently avaiable user mapping is the full user name (e.g. `Joe Smith` vs. `jsmith` as a login) so we leverage that for our user-level stats.

# Notes on writing data using this tool

Every individual series generated with this tool will produce a JSON-compatible object like the following:

```json
{
  "description": "all created PRs by user",
  "labels": {
    "repository_name": "<>",
    "user": "<>"
  },
  "measurement_type": "count",
  "name": "users_total_pull_requests",
  "value": 0
}
```

These produced metrics are analogous to a JSON representation of a prometheus stat (which matches with the OpenMetrics standard we mention above).

## Individual object keys and their usage

* `description`
  * string that gives details about this particular metric (needed for Stackdriver output)
* `labels`
  * `"Key": "Value"` pairs that describe addtional dimensions for querying this metric (directly correlates with "tags" in typical TSDB parlance)
* `measurement_type`
  * what type of measurement are we producing (these are internal relations and cannot be directly leveraged by other systems)
* `name`
  * the actual metric name
* `value`
  * the actual value of the series

## Further discussion of series vs. metrics

To lay this out simply: A metric is comprised of many series. A series is a single example of a metric with all associated labels/tags expanded.

So in our example above, the *metric* is `users_total_pull_requests` while the _series_ is the entire JSON object. Many SaaS systems will charge per _series_ created, not simply per metric, so be mindful of this distinction when storing this data.
