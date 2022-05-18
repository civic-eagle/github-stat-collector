from datetime import timedelta
from copy import deepcopy
import logging

from github_stats.schema import tmp_statobj


class StatsOutput(object):
    def __init__(self, config, timestamp=0.0):
        self.log = logging.getLogger("github-stats.output")
        default_labels = {"repository_name": config["repo"]["name"]}
        self.tmpobj = deepcopy(tmp_statobj)
        self.tmpobj["labels"] = deepcopy(default_labels)
        if timestamp != 0.0:
            self.tmpobj["timestamp"] = timestamp
        self.main_branch = config["repo"]["branches"].get("main", "main")
        self.release_branch = config["repo"]["branches"].get("release", "main")
        self.float_measurements = ["percent", "gauge"]
        self.broken_users = config["repo"].get("broken_users", [])
        self.user_time_filter = config["repo"].get("user_time_filter", False)

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
        formatted_stats = list()
        """
        Simple stats
        example:
         'commits': {'branch_commits': {'branch1": {"total_commits": 2, "window_commits": 1},
                     'total_commits': 3, "window_commits": 1},
         'general': {'main_branch_commits': 1, 'tag_matches': {'release tag': 1}},
         'releases': {'releases': {'v0.1.0': {'author': '',
                                              'body': '',
                                              'created_at': '2022-03-07 19:59:11'}},
                      'total_releases': 1,
                      'total_window_releases': 1},
        """
        commits = stats_object.get("commits", {})
        stat = deepcopy(self.tmpobj)
        stat["name"] = "commits_total"
        stat["type"] = "count"
        stat["value"] = commits["total_commits"]
        stat["description"] = "All commits for the project"
        stat = deepcopy(self.tmpobj)
        formatted_stats.append(stat)
        stat["name"] = "window_commits_total"
        stat["type"] = "gauge"
        stat["value"] = commits["window_commits"]
        stat[
            "description"
        ] = "All commits detected within the initial collection time range"
        formatted_stats.append(stat)
        stat = deepcopy(self.tmpobj)
        stat["name"] = "avg_commit_release_time_secs"
        stat["type"] = "gauge"
        stat["value"] = commits["avg_commit_time"]
        stat["description"] = "Average time between commit and release"
        formatted_stats.append(stat)
        stat = deepcopy(self.tmpobj)
        stat["name"] = "unreleased_commits_count"
        stat["type"] = "gauge"
        stat["value"] = commits["unreleased_commits"]
        stat["description"] = "Any commit that isn't matched to a release"
        formatted_stats.append(stat)
        for branchname, values in commits["branch_commits"].items():
            stat = deepcopy(self.tmpobj)
            stat["name"] = "branch_commits_total"
            stat["value"] = values["total_commits"]
            stat["type"] = "count"
            stat["description"] = "Count of commits to a specific branch"
            stat["labels"]["branch"] = branchname
            formatted_stats.append(stat)
            stat = deepcopy(self.tmpobj)
            stat["name"] = "branch_window_commits_total"
            stat["type"] = "gauge"
            stat["value"] = values["window_commits"]
            stat["description"] = "Count of commits to a specific branch in time range"
            stat["labels"]["branch"] = branchname
            formatted_stats.append(stat)

        general = stats_object.get("general", {})
        stat = deepcopy(self.tmpobj)
        stat["name"] = "main_branch_commits_total"
        stat["type"] = "count"
        stat["value"] = general["main_branch_commits"]
        stat["description"] = "commits to the configured 'main' branch for the repo"
        stat["labels"]["branch_name"] = self.main_branch
        formatted_stats.append(stat)
        stat = deepcopy(self.tmpobj)
        stat["name"] = "main_branch_window_commits_total"
        stat["type"] = "gauge"
        stat["value"] = general["window_main_branch_commits"]
        stat[
            "description"
        ] = "commits to the configured 'main' branch for the repo in time range"
        stat["labels"]["branch_name"] = self.main_branch
        formatted_stats.append(stat)

        releases = stats_object.get("releases", {})
        stat = deepcopy(self.tmpobj)
        stat["name"] = "releases_total"
        stat["type"] = "count"
        stat["value"] = releases["total_releases"]
        stat["description"] = "All releases"
        formatted_stats.append(stat)
        stat = deepcopy(self.tmpobj)
        stat["name"] = "window_releases_total"
        stat["type"] = "gauge"
        stat["value"] = releases["total_window_releases"]
        stat["description"] = "All releases detected within the collection time range"
        formatted_stats.append(stat)

        stat = deepcopy(self.tmpobj)
        stat["name"] = "total_collection_time_secs"
        stat["type"] = "gauge"
        stat["value"] = stats_object["collection_time_secs"]
        stat["description"] = "Total time (in seconds) that collection took"
        formatted_stats.append(stat)

        """
        Pull requests

        example:
         'pull_requests': {
             'avg_pr_time_open_secs': 236275.55798969071,
             'closed_pull_requests': ['pull1', 'pull2'],
             'labels': {'label2': {'pulls': ['pull2'],
                                   'total_prs': 0,
                                   'total_window_prs': 24},
                        'label1': {'pulls': ['pull1'],
                                   'total_prs': 0,
                                   'total_window_prs': 8}},
             'open_pull_requests': ['pull1'],
             'total_window_pull_requests': 81,
             'total_closed_pull_requests': 1510,
             'total_draft_pull_requests': 9,
             'total_merged_pull_requests': 2866,
             'total_open_pull_requests': 7,
             'total_pr_time_open_secs': 366699666.0,
             'total_pull_requests': 1517},
         },
        """
        pulls = stats_object.get("pull_requests", {})

        timetaken = stats_object.get("pull_requests", {}).get("collection_time", 0)
        if timetaken:
            stat = deepcopy(self.tmpobj)
            stat["name"] = "pr_collection_time_secs"
            stat["type"] = "gauge"
            stat["description"] = "seconds taken to collect pull request stats"
            stat["value"] = timetaken
            formatted_stats.append(stat)
        pull_desc = {
            "merged_pull_requests_total": {
                "key": "total_merged_pull_requests",
                "desc": "All PRs merged into the code base",
            },
            "avg_pr_time_open_secs": {
                "desc": "Avg. # of seconds a PR was open",
                "key": "avg_pr_time_open_secs",
                "type": "gauge",
            },
            "window_pull_requests_total": {
                "desc": "PRs updated within the initial collection time range",
                "key": "total_window_pull_requests",
                "type": "gauge",
            },
            "closed_pull_requests_total": {
                "desc": "Closed PRs (merged or otherwise)",
                "key": "total_closed_pull_requests",
            },
            "draft_pull_requests_total": {
                "desc": "PRs in a draft state (includes closed PRs in draft state)",
                "key": "total_draft_pull_requests",
                "type": "gauge",
            },
            "open_pull_requests_total": {
                "desc": "Currently open PRs",
                "key": "total_open_pull_requests",
                "type": "gauge",
            },
            "pull_requests_total": {
                "desc": "All PRs created for the repo",
                "key": "total_pull_requests",
            },
        }
        label_desc = {
            "labelled_prs_total": {
                "desc": "All PRs associated with a label",
                "key": "total_prs",
            },
            "window_labelled_prs_total": {
                "desc": "prs associated with a label within the initial collection time range",
                "type": "gauge",
                "key": "total_window_prs",
            },
        }
        for key, desc in pull_desc.items():
            stat = deepcopy(self.tmpobj)
            stat["name"] = key
            stat["description"] = desc["desc"]
            stat["type"] = desc["type"]
            stat["value"] = pulls[desc["key"]]
            formatted_stats.append(stat)
        for label, data in pulls["labels"].items():
            for k, v in label_desc.items():
                stat = deepcopy(self.tmpobj)
                stat["labels"]["label"] = label
                stat["name"] = k
                stat["type"] = v["type"]
                stat["value"] = data[v["key"]]
                stat["description"] = v["desc"]
                formatted_stats.append(stat)
        """
        Format branches
        example:
        {'branches': {'branches': {'branch1': {'author': '',
                                               'commit': 'd17bc430f443ba9fbc4fb7d71b71bcc3633512e2',
                                               'created': '2022-03-07T21:28:59Z'},
                                   'main': {'author': 'Johnson',
                                            'commit': '16b3eb558ab95f6ec50352c6c58aeddfc3f898d8',
                                            'created': '2022-03-11T17:54:24Z'},
                      'empty_branches': [],
                      'inactive_branches': {'branch2': {'author': ''
                                                       'commit': 'bf49a7d08251488e6379933745de82c108c64c87',
                                                       'created': '2020-11-24T21:50:26Z'}},
         'protected_branches': 1,
         'total_window_branches': 1,
         'total_branches': 3,
         'total_empty_branches': 0}
        """
        descriptions = {
            "protected_branches_total": {
                "desc": "Branches that are protected from direct commits",
                "type": "gauge",
                "key": "protected_branches",
            },
            "window_branches_total": {
                "desc": "branches that have received commits within the initial collection time range",
                "type": "gauge",
                "key": "total_window_branches",
            },
            "branches_total": {
                "desc": "All branches of the project",
                "type": "count",
                "key": "total_branches",
            },
        }
        branches = stats_object.get("branches", {})
        for key, desc in descriptions.items():
            if desc["key"] not in branches:
                continue
            value = branches[desc["key"]]
            stat = deepcopy(self.tmpobj)
            stat["name"] = key
            stat["value"] = value
            stat["type"] = desc["type"]
            stat["description"] = desc["desc"]
            formatted_stats.append(stat)
        timetaken = stats_object.get("branches", {}).get("collection_time", 0)
        if timetaken:
            stat = deepcopy(self.tmpobj)
            stat["name"] = "branches_collection_time_secs"
            stat["description"] = "seconds taken to collect branch stats"
            stat["type"] = "gauge"
            stat["value"] = timetaken
            formatted_stats.append(stat)
        """
        Format workflow stats
        example:
         'workflows': {'events': {'pull_request': 28, 'push': 64, 'schedule': 8},
                       'workflows': {'CI': {'last_run': 3696,
                                            'retries': 9,
                                            'run_cancelled_percentage': 0,
                                            'run_failure_percentage': 29.69,
                                            'run_skipped_percentage': 0,
                                            'run_startup_failure_percentage': 0,
                                            'run_success_percentage': 70.31,
                                            'runs': {'failure': 19, 'success': 45},
                                            'total_window_runs': 64,
                                            'users': [],
                                            'window_runs_of_total_percentage': 1.73},
                                     'Cleanup': {'last_run': 291,
                                                 'retries': 0,
                                                 'run_cancelled_percentage': 0,
                                                 'run_failure_percentage': 0,
                                                 'run_skipped_percentage': 0,
                                                 'run_startup_failure_percentage': 0,
                                                 'run_success_percentage': 100.0,
                                                 'runs': {'success': 8},
                                                 'total_window_runs': 8,
                                                 'users': [],
                                                 'window_runs_of_total_percentage': 2.75},
                                     'security scans': {'last_run': 112,
                                                        'retries': 0,
                                                        'run_cancelled_percentage': 0,
                                                        'run_failure_percentage': 3.57,
                                                        'run_skipped_percentage': 0,
                                                        'run_startup_failure_percentage': 0,
                                                        'run_success_percentage': 96.43,
                                                        'runs': {'failure': 1,
                                                                 'success': 27},
                                                        'total_window_runs': 28,
                                                        'users': [],
                                                        'window_runs_of_total_percentage': 25.0}}}}
        """
        workflow_descriptions = {
            "retries_total": {
                "desc": "Number of workflow retries during initial collection time range",
                "key": "retries",
                "type": "count",
            },
            "run_cancelled_percentage": {
                "desc": "Percentage of runs within collection time range that were cancelled",
                "key": "run_cancelled_percentage",
                "type": "percent",
            },
            "run_failure_percentage": {
                "desc": "Percentage of runs within collection time range that failed",
                "key": "run_failure_percentage",
                "type": "percent",
            },
            "run_skipped_percentage": {
                "desc": "Percentage of runs within collection time range that were skipped",
                "key": "run_skipped_percentage",
                "type": "percent",
            },
            "run_success_percentage": {
                "desc": "Percentage of runs within collection time range that succeeded",
                "key": "run_success_percentage",
                "type": "percent",
            },
            "run_startup_failure_percentage": {
                "desc": "Percentage of runs within collection time range that failed during startup",
                "key": "run_startup_failure_percentage",
                "type": "percent",
            },
            "window_runs_total": {
                "desc": "Total count of runs within collection time range",
                "key": "total_window_runs",
                "type": "count",
            },
            "window_runs_of_total_percentage": {
                "desc": "Percentage of total workflow runs that occurred during collection time range",
                "key": "window_runs_of_total_percentage",
                "type": "percent",
            },
        }

        workflows = stats_object.get("workflows", {})
        timetaken = stats_object.get("workflows", {}).get("collection_time", 0)
        if timetaken:
            stat = deepcopy(self.tmpobj)
            stat["name"] = "workflow_collection_time_secs"
            stat["description"] = "seconds taken to collect workflow stats"
            stat["value"] = timetaken
            formatted_stats.append(stat)
        for k, counts in workflows.get("events", {}).items():
            for key, val in counts.items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = f"workflows_events_{key}"
                if not stat["name"].endswith("total"):
                    stat["name"] += "_total"
                stat["labels"]["event_type"] = k
                stat["value"] = val
                stat["description"] = "Count of workflow events"
                formatted_stats.append(stat)
        for k, v in workflows.get("workflows", {}).items():
            for rtype, val in v["runs"].items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = "workflows_runs_total"
                stat["labels"]["run_type"] = rtype
                stat["labels"]["workflow"] = k
                stat["value"] = val
                stat[
                    "description"
                ] = "Count of runs during the initial collection time range"
            formatted_stats.append(stat)
            for key, desc in workflow_descriptions.items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = f"workflows_{key}"
                stat["labels"]["workflow"] = k
                stat["value"] = v[desc["key"]]
                stat["description"] = desc["desc"]
                stat["measurement_type"] = desc["type"]
                formatted_stats.append(stat)
        """
        Format user/contributor stats

        example:
                   'Jeffries Jefferson': {'branches': [],
                                  'closed_pull_requests': ['pull-1',
                                                           'pull-2'],
                                  'events': {},
                                  'name': '',
                                  'total_merged_pull_requests': 5,
                                  'avg_pr_time_open_secs': 6000,
                                  'total_branches': 0,
                                  'total_closed_pull_requests': 2,
                                  'total_commits': 0,
                                  'total_releases': 0,
                                  'total_window_releases': 0,
                                  'total_open_pull_requests': 0,
                                  'total_pull_requests': 2,
                                  'workflow_totals': {'failure': 1, 'success': 11},
                                  'workflows': {'CI': {'failure': 1, 'success': 7},
                                         'security scans': {'success': 4}}},
        """
        user_descriptions = {
            "window_releases_total": {
                "desc": "all recent releases by a user",
                "key": "total_window_releases",
            },
            "releases_total": {
                "desc": "All releases by a user",
                "key": "total_releases",
            },
            "window_branches_total": {
                "desc": "all existing branches created by user in time range",
                "key": "total_window_branches",
            },
            "branches_total": {
                "desc": "all existing branches created by user",
                "key": "total_branches",
            },
            "closed_pull_requests_total": {
                "desc": "any closed pull requests",
                "key": "total_closed_pull_requests",
            },
            "window_commits_total": {
                "desc": "all commits by user in time range",
                "key": "total_window_commits",
            },
            "commits_total": {
                "desc": "all commits by user",
                "key": "total_commits",
            },
            "avg_user_pr_time_open_secs": {
                "desc": "Avg. # of seconds a PR is open",
                "key": "avg_pr_time_open_secs",
                "type": "gauge",
            },
            "merged_pull_requests_total": {
                "desc": "PRs merged into the code base",
                "key": "total_merged_pull_requests",
            },
            "open_pull_requests_total": {
                "desc": "PRs open in time range by user",
                "key": "total_open_pull_requests",
            },
            "window_pull_requests_total": {
                "desc": "all created PRs by user in time range",
                "key": "total_pull_requests",
            },
            "pull_requests_total": {
                "desc": "all created PRs by user",
                "key": "total_pull_requests",
            },
        }
        td = (
            stats_object["collection_date"] - timedelta(days=stats_object["window"])
        ).timestamp()
        dropped_users = 0
        accepted_users = 0
        for user, data in stats_object.get("users", {}).items():
            if user in self.broken_users:
                self.log.warning(
                    f"{user}'s marked 'broken', skipping tracking their commits"
                )
                continue
            if self.user_time_filter and data["last_commit_time"] < td:
                self.log.warning(
                    f"{user}'s last commit {data['last_commit_time']} outside window {td}. Dropping"
                )
                dropped_users += 1
                continue
            accepted_users += 1
            for wkstat, desc in user_descriptions.items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = f"users_{wkstat}"
                stat["labels"]["user"] = user
                stat["value"] = data[desc["key"]]
                stat["description"] = desc["desc"]
                formatted_stats.append(stat)
            for wktype, value in data["workflow_totals"].items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = "users_workflow_total"
                stat["labels"]["user"] = user
                stat["labels"]["run_type"] = wktype
                stat["value"] = value
                stat["description"] = "total count of workflow runs by a user"
                formatted_stats.append(stat)
            for workflow, wktypes in data["workflows"].items():
                for wktype, value in wktypes.items():
                    stat = deepcopy(self.tmpobj)
                    stat["name"] = "users_workflow_total"
                    stat["labels"]["workflow"] = workflow
                    stat["labels"]["user"] = user
                    stat["labels"]["run_type"] = wktype
                    stat["value"] = value
                    stat[
                        "description"
                    ] = "count of runs for a workflow by a user by workflow result"
                    formatted_stats.append(stat)
        stat = deepcopy(self.tmpobj)
        stat["name"] = "users_dropped"
        stat["value"] = dropped_users
        stat[
            "description"
        ] = "Number of user objects dropped because their commits were outside our window"
        formatted_stats.append(stat)
        stat = deepcopy(self.tmpobj)
        stat["name"] = "users_accepted"
        stat["value"] = dropped_users
        stat["description"] = "Number of user objects with commits in the window"
        formatted_stats.append(stat)

        """
        "Punch card" stats:

         'repo_stats': {
         'code_frequency': {'2022-03-20 00:00:00': {'additions': 389,
                                                           'deletions': -294}},
        """
        for week, counts in (
            stats_object["repo_stats"].get("code_frequency", {}).items()
        ):
            stat = deepcopy(self.tmpobj)
            stat["name"] = "weekly_line_changes_total"
            stat["labels"]["type"] = "additions"
            stat["labels"]["week"] = week
            stat["value"] = counts["additions"]
            stat["description"] = "count of line changes during a week"
            formatted_stats.append(stat)
            stat = deepcopy(self.tmpobj)
            stat["name"] = "weekly_line_changes_total"
            stat["labels"]["type"] = "deletions"
            stat["labels"]["week"] = week
            stat["description"] = "count of line changes during a week"
            # ensure deletion count is positive (so we can do math on it better)
            stat["value"] = abs(counts["deletions"])
            formatted_stats.append(stat)

        """
                'commit_activity': {'2022-03-20 00:00:00': {'daily': {'2022-03-20 00:00:00': 2,
                                                                      '2022-03-21 00:00:00': 7,
                                                                      '2022-03-22 00:00:00': 9,
                                                                      '2022-03-23 00:00:00': 2,
                                                                      '2022-03-24 00:00:00': 0,
                                                                      '2022-03-25 00:00:00': 0,
                                                                      '2022-03-26 00:00:00': 0},
                                                            'total_commits': 20}},
        """
        for week, details in (
            stats_object["repo_stats"].get("commit_activity", {}).items()
        ):
            stat = deepcopy(self.tmpobj)
            stat["name"] = "weekly_commits_total"
            stat["labels"]["week"] = week
            stat["value"] = details["total_commits"]
            stat[
                "description"
            ] = "Total count of commits in a week (will change as a week progresses)"
            formatted_stats.append(stat)
            for day, value in details["daily"].items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = "daily_commits_total"
                stat["labels"]["week"] = week
                stat["labels"]["day"] = day
                stat["value"] = value
                stat[
                    "description"
                ] = "Total count of commits in a week (will change as a week progresses)"
                formatted_stats.append(stat)

        """
                'contributors': {'Jefferson Jeffries': {'total_commits': 400,
                                                  'weeks': {'2022-03-20 00:00:00': {'additions': 9,
                                                                                    'commits': 2,
                                                                                    'deletions': 5}}}},
        """
        for name, details in stats_object["repo_stats"].get("contributors", {}).items():
            stat = deepcopy(self.tmpobj)
            stat["name"] = "contributor_commits_total"
            stat["labels"]["name"] = name
            stat["value"] = details["total_commits"]
            stat["description"] = "Total commits from a contributor"
            formatted_stats.append(stat)
            for week, wd in details["weeks"].items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = "weekly_contributor_commits_total"
                stat["labels"]["name"] = name
                stat["labels"]["week"] = week
                stat["description"] = "Weekly commits made by a contributor"
                stat["value"] = wd["commits"]
                formatted_stats.append(stat)
                stat = deepcopy(self.tmpobj)
                stat["name"] = "weekly_contributor_line_changes_total"
                stat["labels"]["name"] = name
                stat["labels"]["week"] = week
                stat["labels"]["type"] = "additions"
                stat["description"] = "Weekly line changes made by a contributor"
                stat["value"] = wd["additions"]
                formatted_stats.append(stat)
                stat = deepcopy(self.tmpobj)
                stat["name"] = "weekly_contributor_line_changes_total"
                stat["labels"]["name"] = name
                stat["labels"]["week"] = week
                stat["labels"]["type"] = "deletions"
                stat["description"] = "Weekly line changes made by a contributor"
                # ensure deletion count is positive (so we can do math on it better)
                stat["value"] = abs(wd["deletions"])
                formatted_stats.append(stat)

        """
                'punchcard': {'days': {'Friday': {0: 46,
                                                  1: 20,
                                                  2: 6,
                                                  3: 0,
                                                  4: 3,
                                                  5: 5,
                                                  6: 6,
                                                  7: 7,
                                                  8: 12,
                                                  9: 39,
                                                  10: 65,
                                                  11: 109,
                                                  12: 85,
                                                  13: 108,
                                                  14: 109,
                                                  15: 123,
                                                  16: 145,
                                                  17: 140,
                                                  18: 113,
                                                  19: 62,
                                                  20: 62,
                                                  21: 48,
                                                  22: 54,
                                                  23: 41,
                                                  'busiest_hour': 16,
                                                  'total_commits': 1408},
                                       'Wednesday': {0: 45,
                                                     1: 29,
                                                     2: 10,
                                                     3: 8,
                                                     4: 13,
                                                     5: 5,
                                                     6: 3,
                                                     7: 3,
                                                     8: 11,
                                                     9: 29,
                                                     10: 67,
                                                     11: 100,
                                                     12: 107,
                                                     13: 143,
                                                     14: 157,
                                                     15: 165,
                                                     16: 150,
                                                     17: 153,
                                                     18: 106,
                                                     19: 58,
                                                     20: 63,
                                                     21: 64,
                                                     22: 49,
                                                     23: 45,
                                                     'busiest_hour': 15,
                                                     'total_commits': 1583}},
                              'sorted_days': [('Thursday', 1610),
                                              ('Wednesday', 1583),
                                              ('Friday', 1408),
                                              ('Tuesday', 1381),
                                              ('Saturday', 1141),
                                              ('Monday', 223),
                                              ('Sunday', 202)],
        """
        punchcard = stats_object["repo_stats"].get("punchcard", {})
        for dayslug, day in punchcard["days"].items():
            stat = deepcopy(self.tmpobj)
            stat["name"] = "punchcard_daily_commits_total"
            stat["description"] = "punchcard count of commits per day"
            stat["labels"]["day"] = dayslug
            stat["value"] = day["total_commits"]
            formatted_stats.append(stat)
            stat = deepcopy(self.tmpobj)
            stat["name"] = "punchcard_daily_busiest_hour"
            stat["description"] = "the UTC-based hour (per day) with the most commits"
            stat["labels"]["day"] = dayslug
            stat["value"] = day["busiest_hour"]
            formatted_stats.append(stat)
        timetaken = stats_object.get("repo_stats", {}).get("collection_time", 0)
        if timetaken:
            stat = deepcopy(self.tmpobj)
            stat["name"] = "punchard_collection_time_secs"
            stat["description"] = "seconds taken to collect punchcard stats"
            stat["value"] = timetaken
            formatted_stats.append(stat)

        return formatted_stats

    def write_stats(self, formatted_stats):
        """
        Actually write stats to output
        """
        pass
