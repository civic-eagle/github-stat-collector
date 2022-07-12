from datetime import timedelta
from copy import deepcopy
import logging
from pprint import pformat

from github_stats.schema import tmp_statobj, user_schema


class StatsOutput(object):
    def __init__(self, config, timestamp=0.0):
        self.log = logging.getLogger("github-stats.output")
        default_labels = {"repository_name": config["repo"]["name"]}
        self.tmpobj = deepcopy(tmp_statobj)
        self.tmpobj["labels"] = deepcopy(default_labels)
        if timestamp > 0.0:
            self.tmpobj["timestamp"] = timestamp
        self.prefix = config.get("metric_prefix", "")
        self.main_branch = config["repo"]["branches"].get("main", "main")
        self.release_branch = config["repo"]["branches"].get("release", "main")
        self.broken_users = config["repo"].get("broken_users", [])
        time_filter = config["repo"].get("user_time_filter_days", False)
        if time_filter:
            self.user_time_filter = timedelta(days=time_filter)
        else:
            self.user_time_filter = None
        self.dropped_users = 0
        self.accepted_users = 0

    def _recurse_stats(self, stats_object, prefix=""):
        """
        Hacky recursion to find and somewhat format
        all incoming stats
        Doing this means we don't have to manually add stats as they change

        :returns: metric name and value
        :rtype: tuple
        """

        if self.user_time_filter:
            td = (stats_object["collection_date"] - self.user_time_filter).timestamp()
        for name, value in stats_object.items():
            if name in self.skip_keys:
                continue
            self.log.debug(f"Processing {name=}, {value=}")
            if prefix:
                new_prefix = f"{prefix}_{name}"
            else:
                new_prefix = str(name)
            if isinstance(value, dict):
                if self.user_time_filter and value.keys() == user_schema.keys():
                    if value["last_commit_time_secs"] < td:
                        self.log.warning(
                            f"{value['user']}'s last commit time ({value['last_commit_time_secs']}) outside filter window...dropping"
                        )
                        self.dropped_users += 1
                        continue
                    else:
                        self.accepted_users += 1
                yield from self._recurse_stats(value, new_prefix)
            else:
                if not isinstance(value, float) and not isinstance(value, int):
                    # skip any values that aren't actually...you know...values
                    self.log.debug(
                        f"Skipping {value} (for {name}) because it isn't a number"
                    )
                    continue
                yield new_prefix, value

    def format_stats(self, stats_object):
        """
        function to ensure all out-going stats
        are in a consistent format

        The basic idea being we can convert a massive
        dictionary object into a list of individual stats

        call this within an overridden subobject like so:

        formatted_stats = super().format_stats(stats_object)

        Then we can process any additional stats or formatting
        changes needed for individual outputs.

        basic format for returned stats:
             {'description': 'punchcard count of commits per day',
              'labels': {'day': 'Sunday', 'repository_name': 'repo1'},
              'measurement_type': 'count',
              'name': 'punchcard_daily_commits_total',
              'value': 202},

        :returns: list of stats ready to ship
        :rtype: list
        """
        formatted_stats = list()
        for k, v in self._recurse_stats(stats_object):
            if k in self.broken_users:
                self.log.warning(
                    f"{k} is marked 'broken', skipping tracking their commits"
                )
                continue
            stat = deepcopy(self.tmpobj)
            if k.startswith("repo_stats_"):
                """
                repo_stats_contributors_dependabot[bot]_weeks_2022-06-26 00:00:00_additions
                repo_stats_commit_activity_2022-06-26 00:00:00_daily_2022-06-28 00:00:00
                repo_stats_code_frequency_2022-06-26 00:00:00_additions
                """
                continue
            elif k.startswith("commits_branch_commits_"):
                """
                Branch commit stats...
                come in like:
                commits_branch_commits_upgrade-craco-esbuild_commits_total
                """
                pass
            elif k.startswith("pull_requests_labels_"):
                """
                PR stats:
                pull_requests_labels_infrastructure_labelled_prs_total
                """
                continue
            elif k.startswith("users_"):
                """
                user stats are interesting...
                users_mothalit_merged_pull_requests_total
                users_dependabot[bot]_workflows_security scans_skipped
                """
                # chunks = k.removeprefix("users_")
                continue
            elif k.startswith("workflows_workflows_"):
                """
                workflow stats
                workflows_.github/workflows/ci.yml_run_startup_failure_percentage
                workflows_workflows_.github/workflows/ci.yml_<stat>
                """
                chunks = k.split("_")[:2]
                name = "_".join(k.split("_")[2:])
                k = f"workflows_{name}"
                stat["labels"]["workflow"] = chunks[-1]
            elif k.startswith("workflows_"):
                """
                workflow stats
                workflows_.github/workflows/ci.yml_run_startup_failure_percentage
                workflows_workflows_.github/workflows/ci.yml_<stat>
                """
                continue
                chunks = k.split("_")[:2]
                name = "_".join(k.split("_")[2:])
                k = f"workflows_{name}"
                stat["labels"]["workflow"] = chunks[-1]
            if self.prefix:
                stat["name"] = f"{self.prefix}_{k}"
            else:
                stat["name"] = k
            # because of earlier assumptions, we can switch type safely
            if not k.endswith("total"):
                stat["measurement_type"] = "gauge"
            stat["value"] = v
            formatted_stats.append(stat)
        self.log.info(pformat(formatted_stats))
        exit(1)
        return formatted_stats

    def write_stats(self, formatted_stats):
        """
        Actually write stats to output
        """
        pass
