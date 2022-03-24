from copy import deepcopy
import logging


class StatsOutput(object):
    def __init__(self, config):
        self.log = logging.getLogger("github-stats.output")
        default_labels = {"repository_name": config["repo"]["name"]}
        self.tmpobj = {
            "name": "",
            "labels": default_labels,
            "value": 0,
            "description": "",
            "measurement_type": "count",
        }
        self.main_branch = config["repo"]["branches"].get("main", "main")
        self.release_branch = config["repo"]["branches"].get("release", "main")

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

        :returns: list of stats ready to ship
        :rtype: list
        """
        formatted_stats = list()
        """
        Simple stats
        example:
         'commits': {'branch_commits': {'branch1": 2},
                     'total_commits': 3},
         'general': {'main_branch_commits': 1, 'tag_matches': {'release tag': 1}},
         'releases': {'releases': {'v0.1.0': {'author': '',
                                              'body': '',
                                              'created_at': '2022-03-07 19:59:11'}},
                      'total_releases': 1},
        """
        commits = stats_object.get("commits", {})
        stat = deepcopy(self.tmpobj)
        stat["name"] = "total_commits"
        stat["value"] = commits["total_commits"]
        stat[
            "description"
        ] = "All commits detected within the initial collection time range"
        formatted_stats.append(stat)
        for branchname, count in commits["branch_commits"].items():
            stat = deepcopy(self.tmpobj)
            stat["name"] = "branch_commits"
            stat["value"] = count
            stat["description"] = "Count of recent commits to a specific branch"
            stat["labels"]["branch"] = branchname
            formatted_stats.append(stat)

        general = stats_object.get("general", {})
        stat = deepcopy(self.tmpobj)
        stat["name"] = "main_branch_commits"
        stat["value"] = general["main_branch_commits"]
        stat["description"] = "commits to the configured 'main' branch for the repo"
        stat["labels"]["branch_name"] = self.main_branch
        formatted_stats.append(stat)

        releases = stats_object.get("releases", {})
        stat = deepcopy(self.tmpobj)
        stat["name"] = "total_releases"
        stat["value"] = releases["total_releases"]
        stat[
            "description"
        ] = "All releases detected within the initial collection time range"
        formatted_stats.append(stat)
        """
        Pull requests

        example:
         'pull_requests': {
             'closed_pull_requests': ['pull1', 'pull2'],
             'labels': {'label2': {'pulls': ['pull2'],
                                   'total_old_prs': 0,
                                   'total_prs': 0,
                                   'total_recent_prs': 24},
                        'label1': {'pulls': ['pull1'],
                                   'total_old_prs': 0,
                                   'total_prs': 0,
                                   'total_recent_prs': 8}},
             'open_pull_requests': ['pull1'],
             'total_active_pull_requests': 81,
             'total_closed_pull_requests': 1510,
             'total_draft_pull_requests': 9,
             'total_inactive_pull_requests': 1436,
             'total_open_pull_requests': 7,
             'total_pull_requests': 1517},
         },
        """
        pulls = stats_object.get("pull_requests", {})
        pull_desc = {
            "total_active_pull_requests": "PRs updated within the initial collection time range",
            "total_closed_pull_requests": "Closed PRs (merged or otherwise)",
            "total_draft_pull_requests": "PRs in a draft state (includes closed PRs in draft state)",
            "total_open_pull_requests": "Currently open PRs",
            "total_inactive_pull_requests": "PRs updated outside the initial collection time range",
            "total_pull_requests": "All PRs created for the repo",
        }
        label_desc = {
            "total_old_prs": "prs associated with a label outside the initial collection time range",
            "total_prs": "All PRs associated with a label",
            "total_recent_prs": "prs associated with a label within the initial collection time range",
        }
        for key, desc in pull_desc.items():
            stat = deepcopy(self.tmpobj)
            stat["name"] = key
            stat["description"] = desc
            stat["value"] = pulls[key]
            formatted_stats.append(stat)
        for label, data in pulls["labels"].items():
            for k, v in label_desc.items():
                stat = deepcopy(self.tmpobj)
                stat["labels"]["label"] = label
                stat["name"] = k
                stat["value"] = data[k]
                stat["description"] = v
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
                                                       'created': '2020-11-24T21:50:26Z'},
         'protected_branches': 1,
         'total_active_branches': 1,
         'total_branches': 3,
         'total_empty_branches': 0,
         'total_inactive_branches': 1}
        """
        descriptions = {
            "protected_branches": "Branches that are protected from direct commits",
            "total_active_branches": "branches that have received commits within the initial collection time range",
            "total_branches": "All branches of the project",
            "total_inactive_branches": "branches that have not received commits within the initial collection time range",
        }
        branches = stats_object.get("branches", {})
        for key, description in descriptions.items():
            if key not in branches:
                continue
            value = branches[key]
            stat = deepcopy(self.tmpobj)
            stat["name"] = f"branches.{key}"
            stat["value"] = value
            stat["description"] = description
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
            "retries": "Number of workflow retries during initial collection time range",
            "run_cancelled_percentage": "Percentage of runs within collection time range that were cancelled",
            "run_failure_percentage": "Percentage of runs within collection time range that failed",
            "run_skipped_percentage": "Percentage of runs within collection time range that were skipped",
            "run_success_percentage": "Percentage of runs within collection time range that succeeded",
            "run_startup_failure_percentage": "Percentage of runs within collection time range that failed during startup",
            "total_window_runs": "Total count of runs within collection time range",
            "window_runs_of_total_percentage": "Percentage of total workflow runs that occurred during collection time range",
        }

        workflows = stats_object.get("workflows", {})
        for k, v in workflows.get("events", {}).items():
            stat = deepcopy(self.tmpobj)
            stat["name"] = "workflows.events"
            stat["labels"]["event_type"] = k
            stat["value"] = v
            stat[
                "description"
            ] = "Count of events during the initial collection time range"
            formatted_stats.append(stat)
        for k, v in workflows.get("workflows", {}).items():
            for rtype, val in v["runs"].items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = "workflows.runs"
                stat["labels"]["run_type"] = rtype
                stat["labels"]["workflow"] = k
                stat["value"] = val
                stat[
                    "description"
                ] = "Count of runs during the initial collection time range"
            formatted_stats.append(stat)
            for key, desc in workflow_descriptions.items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = f"workflows.{key}"
                stat["labels"]["workflow"] = k
                stat["value"] = v[key]
                stat["description"] = desc
                if "percentage" in key:
                    stat["measurement_type"] = "percent"
                formatted_stats.append(stat)
        """
        Format user/contributor stats

        example:
                   'Jeffries Jefferson': {'branches': [],
                                  'closed_pull_requests': ['pull-1',
                                                           'pull-2'],
                                  'events': {},
                                  'inactive_branches': [],
                                  'name': '',
                                  'open_pull_requests': [],
                                  'total_branches': 0,
                                  'total_closed_pull_requests': 2,
                                  'total_commits': 0,
                                  'total_inactive_branches': 0,
                                  'total_open_pull_requests': 0,
                                  'total_pull_requests': 2,
                                  'workflow_totals': {'failure': 1, 'success': 11},
                                  'workflows': {'CI': {'failure': 1, 'success': 7},
                                         'security scans': {'success': 4}}},
        """
        user_descriptions = {
            "total_branches": "all existing branches created by user",
            "total_closed_pull_requests": "any closed pull requests",
            "total_commits": "all commits by user",
            "total_inactive_branches": "branches that haven't been used in time range",
            "total_open_pull_requests": "PRs open in time range by user",
            "total_pull_requests": "all created PRs by user",
        }
        for user, data in stats_object.get("users", {}).items():
            for wkstat, desc in user_descriptions.items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = f"users.{wkstat}"
                stat["labels"]["user"] = user
                stat["value"] = data[wkstat]
                stat["description"] = desc
                formatted_stats.append(stat)
            for wktype, value in data["workflow_totals"].items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = "users.workflow_total"
                stat["labels"]["user"] = user
                stat["labels"]["run_type"] = wktype
                stat["value"] = value
                stat[
                    "description"
                ] = "total count of workflow runs by a user in the initial collection time range"
                formatted_stats.append(stat)
            for workflow, wktypes in data["workflows"].items():
                for wktype, value in wktypes.items():
                    stat = deepcopy(self.tmpobj)
                    stat["name"] = "users.workflows"
                    stat["labels"]["workflow"] = workflow
                    stat["labels"]["user"] = user
                    stat["labels"]["run_type"] = wktype
                    stat["value"] = value
                    stat[
                        "description"
                    ] = "count of runs for a workflow by a user in the initial collection time range"
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
            stat["name"] = "total_weekly_line_changes"
            stat["labels"]["week"] = week
            stat["labels"]["type"] = "additions"
            stat[
                "description"
            ] = "The total count of line changes made during the week (value may change as a week progresses)"
            stat["value"] = counts["additions"]
            formatted_stats.append(stat)
            stat = deepcopy(self.tmpobj)
            stat["name"] = "total_weekly_line_changes"
            stat["labels"]["week"] = week
            stat["labels"]["type"] = "deletions"
            stat["value"] = counts["deletions"]
            stat[
                "description"
            ] = "The total count of line changes made during the week (value may change as a week progresses)"
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
            stat["name"] = "total_weekly_commits"
            stat["labels"]["week"] = week
            stat["value"] = details["total_commits"]
            stat[
                "description"
            ] = "Total count of commits in a week (will change as a week progresses)"
            formatted_stats.append(stat)
            for day, value in details["daily"].items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = "total_daily_commits"
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
            stat["name"] = "total_contributor_commits"
            stat["labels"]["name"] = name
            stat["value"] = details["total_commits"]
            stat["description"] = "Total commits from a contributor"
            formatted_stats.append(stat)
            for week, wd in details["weeks"].items():
                stat = deepcopy(self.tmpobj)
                stat["name"] = "total_weekly_contributor_commits"
                stat["labels"]["name"] = name
                stat["labels"]["week"] = week
                stat["description"] = "Weekly commits made by a contributor"
                stat["value"] = wd["commits"]
                formatted_stats.append(stat)
                stat = deepcopy(self.tmpobj)
                stat["name"] = "total_weekly_contributor_additions"
                stat["labels"]["name"] = name
                stat["labels"]["week"] = week
                stat["description"] = "Weekly additions made by a contributor"
                stat["value"] = wd["additions"]
                formatted_stats.append(stat)
                stat = deepcopy(self.tmpobj)
                stat["name"] = "total_weekly_contributor_deletions"
                stat["labels"]["name"] = name
                stat["labels"]["week"] = week
                stat["description"] = "Weekly deletions made by a contributor"
                stat["value"] = wd["deletions"]
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
        # punch = stats_object["repo_stats"].get("punchcard", {})

        return formatted_stats

    def write_stats(self, formatted_stats):
        """
        Actually write stats to output
        """
        pass
