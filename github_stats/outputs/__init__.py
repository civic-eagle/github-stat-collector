# from datetime import timedelta
from copy import deepcopy
import logging
from pprint import pformat

from github_stats.schema import tmp_statobj


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
        """
        portions of the incoming stat structure that don't match regular
        formatting, so we need to handle them separately
        """
        # self.user_time_filter = config["repo"].get("user_time_filter", False)

    def _recurse_stats(self, stats_object, prefix=""):
        for name, value in stats_object.items():
            if name in self.skip_keys:
                continue
            self.log.debug(f"Processing {name=}, {value=}")
            if prefix:
                new_prefix = f"{prefix}_{name}"
            else:
                new_prefix = str(name)
            if isinstance(value, dict):
                yield from self._recurse_stats(value, new_prefix)
            else:
                if not isinstance(value, float) and not isinstance(value, int):
                    # skip any values that aren't actually...you know...values
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

        Each "section" below is simply a group of metrics being
        re-formatted from the initial collection. Sectioning just helps
        us find groups easier

        basic format for returned stats:
             {'description': 'punchcard count of commits per day',
              'labels': {'day': 'Sunday', 'repository_name': 'repo1'},
              'measurement_type': 'count',
              'name': 'punchcard_daily_commits_total',
              'value': 202},

        :returns: list of stats ready to ship
        :rtype: list
        """
        # drop users whose commits are outside a defined window
        # td = (
        #     stats_object["collection_date"] - timedelta(days=stats_object["window"])
        # ).timestamp()
        # dropped_users = 0
        # accepted_users = 0
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
                continue
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
