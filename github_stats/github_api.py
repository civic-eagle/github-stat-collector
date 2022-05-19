"""
A general note:
    We aren't using DefaultDicts in this code base because it was difficult to suss
    out how to set an increment value (+= 1) on a new dictionary key, so
    instead we use the tried and true "if key not in dict" pattern.

    Of course, this pattern isn't perfect, and can be a bit confusing to read at times.
"""
import calendar
from copy import deepcopy
from datetime import datetime, timedelta
import logging
import os
import pprint
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import time
import urllib.parse

from github_stats.schema import user_schema
from github_stats.schema import user_login_cache as user_login_cache_schema
from github_stats.schema import stats as stats_schema
from github_stats.schema import DEFAULT_WINDOW
from github_stats.gitops import Repo
from github_stats.util import load_patterns

calendar.setfirstweekday(calendar.SUNDAY)


class GithubAccess(object):
    BASE_URL = "https://api.github.com/"

    def __init__(self, config):
        auth_token = os.environ.get("GITHUB_TOKEN", None)
        if not auth_token:
            auth_token = config["repo"].get("github_token", None)
        if not auth_token:
            raise Exception("Cannot find Github auth token in environment or config")

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {auth_token}",
        }
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 503, 504, 429),
            method_whitelist=["GET"],
        )
        self._request = requests.Session()
        adapter = HTTPAdapter(max_retries=retry)
        self._request.mount("https://", adapter)
        self._request.headers.update(headers)
        self.repo = Repo(config)

        self.org = config["repo"]["org"]
        self.repo_name = f"{self.org}/{config['repo']['name']}"
        self.log = logging.getLogger("github-stats.collection")
        self.ignored_workflows = config["repo"].get("ignored_workflows", list())
        self.ignored_statuses = config["repo"].get("ignored_statuses", ["queued"])
        self.main_branch = config["repo"]["branches"].get("main", "main")
        self.release_branch = config["repo"]["branches"].get("release", "main")
        self.non_user_events = config["repo"].get("non_user_events", ["schedule"])
        self.per_page = config.get("query", {}).get("results_per_page", 100)
        self.special_logins = config["repo"].get("special_logins", {})
        self.special_names = {v: k for k, v in self.special_logins.items()}
        self.broken_users = config["repo"].get("broken_users", [])

        self.tag_matches, self.bug_matches, self.pr_matches = load_patterns(
            config["repo"].get("tag_patterns", []),
            config["repo"].get("bug_matching", {}),
        )

        """
        Many label matching patterns
        """
        self.label_matches = {
            labelname: labels
            for labelname, labels in config["repo"].get("additional_labels", {}).items()
        }

        """
        Actual stats object
        """
        self.contributor_collection_time = 0
        self.user_login_cache = deepcopy(user_login_cache_schema)
        self.stats = deepcopy(stats_schema)
        self.stats["pull_requests"]["labels"] = {
            label: {
                "total_window_prs": 0,
                "total_prs": 0,
            }
            for label in self.label_matches
        }
        self.stats["general"]["tag_matches"] = {t: 0 for t in self.tag_matches.keys()}
        self.starttime = time.time()
        self._load_contributors()

    def _retry_empty(self, url):
        """
        Occasionally cold-cache queries to Github return empty results.
        We'll set up a retry loop to avoid that (since the built-in
        requests retry object can't retry on results values)
        This wrapper also gives us an easy place to add a default
        timeout to the requests calls without having to set up
        a whole timeout object.
        """
        for retry in range(0, 3):
            res = self._request.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data:
                return data, res.links
        else:
            return [], {}

    def _github_query(self, url, key=None, params=None):
        """
        Query paginated endpoint from Github

        We'll make a generator here to reduce memory pressure
        and allow for faster results processing
        """
        if not params:
            params = {}
        params["per_page"] = self.per_page
        url = urllib.parse.urljoin(self.BASE_URL, url.strip("/"))
        self.log.debug(f"Requesting {url}")
        req = requests.models.PreparedRequest()
        req.prepare_url(url, params)
        data, links = self._retry_empty(req.url)
        datatype = type(data)
        if key and datatype == dict and key in data:
            if isinstance(data[key], list):
                for k in data[key]:
                    yield k
            else:
                yield data[key]
        elif datatype == list:
            for k in data:
                yield k
        else:
            # just return the entire object as a default
            yield data

        next_url = links.get("next", dict()).get("url", "")
        while next_url:
            self.log.debug(f"Requesting {next_url}")
            data, links = self._retry_empty(next_url)
            datatype = type(data)
            if key and datatype == dict and key in data:
                if isinstance(data[key], list):
                    for k in data[key]:
                        yield k
                else:
                    yield data[key]
            elif isinstance(data, list):
                for k in data:
                    yield k
            else:
                yield data
            next_url = links.get("next", dict()).get("url", "")

    def _cache_user_login(self, login):
        """
        Return user's name based on their Github login
        (this is so we can avoid having two keys for the same user)

        :returns: User's name
        :rtype: str
        """
        if login in self.user_login_cache["logins"]:
            return self.user_login_cache["logins"][login]
        url = f"/users/{login}"
        try:
            user = [u for u in self._github_query(url)][0]
        except Exception as e:
            self.log.warning(f"{login} doesn't match a Github user! {e}")
            return ""
        self.log.debug(f"Caching {user} for {login}")
        name = user["name"] or login
        if not user["name"] and name in self.special_names:
            name = self.special_names[name]
        self.user_login_cache["logins"][login] = name
        self.user_login_cache["names"][name] = login
        if name not in self.stats["users"]:
            self.stats["users"][name] = deepcopy(user_schema)
        self.log.debug(f"Returned name: {self.user_login_cache['logins'][login]}")
        return self.user_login_cache["logins"][login]

    def _cache_user_name(self, name):
        """
        Return user's actual login based on their Github name
        (this is so we can avoid having two keys for the same user)

        :returns: User's name
        :rtype: str
        """
        if name in self.user_login_cache["names"]:
            return self.user_login_cache["logins"][self.user_login_cache["names"][name]]
        if name in self.user_login_cache["logins"]:
            return self.user_login_cache["logins"][name]
        if name in self.special_logins:
            return self.user_login_cache["logins"][self.special_logins[name]]
        raise Exception(
            f"User {name} doesn't exist in cache or in {self.special_logins}!"
        )

    def _load_contributors(self):
        """
        Configure all users that have commits into the repo

        This is a "prep" step

        :returns: None
        """
        self.log.info("Loading repo contributors...")
        starttime = time.time()
        url = f"/repos/{self.repo_name}/contributors"
        for contributor in self._github_query(url):
            # we rely on the caching function to add the user properly
            _ = self._cache_user_login(contributor["login"])
        self.stats["users"]["unknown"] = deepcopy(user_schema)
        self.contributor_collection_time = time.time() - starttime
        self.log.info(
            f"Loaded contributors in {self.contributor_collection_time} seconds"
        )

    def _set_collection_date(self, date, window):
        if not self.stats["collection_date"]:
            self.stats["collection_date"] = date
            self.log.debug(f"Collection timestamp: {date}")
        if not self.stats["window"]:
            self.stats["window"] = window * 4
            self.log.debug(f"Collection window: {window}")

    def load_all_stats(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        Wrapper to execute all stat collection functions

        :returns: None
        """
        self._set_collection_date(base_date, window)
        self.load_commits(base_date, window)
        self.load_branches(base_date, window)
        self.load_repo_stats(base_date, window)
        self.load_pull_requests(base_date, window)
        self.load_releases(base_date, window)
        self.load_workflow_runs(base_date, window)
        self.stats["collection_time_secs"] = time.time() - self.starttime

    def load_pull_requests(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        Collect pull request data

        Because we want to see older pull requests as well, we don't
        filter the initial query based on time here

        :returns: None
        """
        self._set_collection_date(base_date, window)
        td = base_date - timedelta(days=window)
        starttime = time.time()
        self.log.info("Loading Pull Request Data...")
        url = f"/repos/{self.repo_name}/pulls"
        for pull in self._github_query(url, params={"state": "all"}):
            created = datetime.strptime(pull["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            if created > base_date:
                self.log.debug(f"{pull['title']} was created in the future. Skipping")
                continue
            modified_time = datetime.strptime(pull["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
            self.stats["pull_requests"]["total_pull_requests"] += 1
            if pull["draft"]:
                self.stats["pull_requests"]["total_draft_pull_requests"] += 1
            author = self._cache_user_login(pull["user"]["login"])
            self.stats["users"][author]["total_pull_requests"] += 1
            if (
                modified_time.date() < base_date.date()
                and modified_time.date() > td.date()
            ):
                self.stats["pull_requests"]["total_window_pull_requests"] += 1
                self._process_labels(pull["title"], pull["labels"], "total_old_prs")
                self.stats["users"][author]["total_window_pull_requests"] += 1
            for label in pull["labels"]:
                name = label["name"]
                for labelname, matches in self.label_matches.items():
                    if name not in matches:
                        continue
                    self.log.debug(f"{pull['title']}: {name} ({matches=}) for {label}")
                    self.stats["pull_requests"]["labels"][labelname]["total_prs"] += 1
                    if (
                        modified_time.date() < base_date.date()
                        and modified_time.date() > td.date()
                    ):
                        self.stats["pull_requests"]["labels"][labelname][
                            "total_window_prs"
                        ] += 1
                if name not in self.label_matches.keys():
                    if name not in self.stats["pull_requests"]["labels"]:
                        self.stats["pull_requests"]["labels"][name] = {
                            "total_prs": 1,
                            "total_window_prs": 0,
                        }
                    else:
                        self.stats["pull_requests"]["labels"][name]["total_prs"] += 1
                    if (
                        modified_time.date() < base_date.date()
                        and modified_time.date() > td.date()
                    ):
                        self.stats["pull_requests"]["labels"][name][
                            "total_window_prs"
                        ] += 1

            """
            Calculate avg PR time
            """
            created = datetime.strptime(pull["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            merged = pull.get("merged_at", None)
            if not merged:
                closed = pull.get("closed_at", None)
            else:
                self.stats["pull_requests"]["total_merged_pull_requests"] += 1
            if merged or closed:
                if merged:
                    endtime = datetime.strptime(merged, "%Y-%m-%dT%H:%M:%SZ")
                else:
                    endtime = datetime.strptime(closed, "%Y-%m-%dT%H:%M:%SZ")
                timeopen = (endtime - created).total_seconds()
                self.stats["pull_requests"]["total_pr_time_open_secs"] += timeopen
                self.stats["users"][author]["total_pr_time_open_secs"] += timeopen

            """
            We'll be explicit about state here to avoid
            changed state values affecting this later
            """
            if pull["state"] == "open":
                self.stats["pull_requests"]["total_open_pull_requests"] += 1
                self.stats["users"][author]["total_open_pull_requests"] += 1
            elif not merged and pull["state"] == "closed":
                self.stats["pull_requests"]["total_closed_pull_requests"] += 1
                self.stats["users"][author]["total_closed_pull_requests"] += 1
            elif pull["state"] == "closed":
                self.stats["pull_requests"]["total_merged_pull_requests"] += 1
                self.stats["users"][author]["total_merged_pull_requests"] += 1
        """
        Generate average PR time after collecting all stats
        to get better numbers
        """
        if self.stats["pull_requests"]["total_pull_requests"] > 0:
            self.stats["pull_requests"]["avg_pr_time_open_secs"] = (
                self.stats["pull_requests"]["total_pr_time_open_secs"]
                / self.stats["pull_requests"]["total_pull_requests"]
            )
        for user, data in self.stats["users"].items():
            if data["total_pull_requests"] > 0:
                self.stats["users"][user]["avg_pr_time_open_secs"] = (
                    data["total_pr_time_open_secs"] / data["total_pull_requests"]
                )
        self.stats["pull_requests"]["collection_time"] = time.time() - starttime
        self.log.info(
            f"Loaded pull requests in {self.stats['pull_requests']['collection_time']} seconds"
        )

    def load_commits(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        Collect commit log from pygit2
        This will not be a perfect representation of commits, but should
        give us *some* sense of who's working on what

        While this does essentially mirror some behavior in load_branches, we should
        keep the two functions separate so we _can_ alter them individually later

        :returns: None
        """
        self._set_collection_date(base_date, window)
        td = base_date - timedelta(days=window)
        td_ts = td.timestamp()
        base_ts = base_date.timestamp()
        starttime = time.time()
        self.log.info("Loading commit details...")
        self.stats["commits"]["collection_time"] = time.time() - starttime
        for branchdata in self.repo.list_branches():
            branch, last_commit = branchdata
            self.log.debug(f"Processing commits to {branch}")
            for commit in self.repo.branch_commit_log(branch):
                if commit["time"] > base_ts:
                    self.log.debug(
                        f"{commit['hash']} for {commit['author']} is in the future. Skipping"
                    )
                    continue
                try:
                    user = self._cache_user_name(commit["author"].split(" <")[0])
                except Exception:
                    user = "unknown"
                self.stats["users"][user]["total_commits"] += 1
                if commit["time"] > self.stats["users"][user]["last_commit_time"]:
                    self.stats["users"][user]["last_commit_time"] = commit["time"]
                if td_ts < commit["time"] < base_ts:
                    self.stats["commits"]["window_commits"] += 1
                    self.stats["users"][user]["total_window_commits"] += 1
                if branch in self.stats["commits"]["branch_commits"]:
                    self.stats["commits"]["branch_commits"][branch][
                        "total_commits"
                    ] += 1
                    if td_ts < commit["time"] < base_ts:
                        self.log.debug(f"Window commit: {pprint.pformat(commit)}")
                        self.stats["commits"]["branch_commits"][branch][
                            "window_commits"
                        ] += 1
                else:
                    self.stats["commits"]["branch_commits"][branch] = {
                        "total_commits": 1,
                        "window_commits": 0,
                    }
                    if td_ts < commit["time"] < base_ts:
                        self.stats["commits"]["branch_commits"][branch][
                            "window_commits"
                        ] += 1

        (
            avg_commit_time,
            unreleased_commits,
            total_commits,
        ) = self.repo.commit_release_matching()
        self.stats["commits"]["avg_commit_time"] = avg_commit_time
        self.stats["commits"]["unreleased_commits"] = unreleased_commits
        self.stats["commits"]["collection_time"] = time.time() - starttime
        self.stats["commits"]["total_commits"] = total_commits
        self.log.info(
            f"Loaded commit history in {self.stats['commits']['collection_time']} seconds"
        )

    def load_branches(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        Because getting branch details requires a second
        query, this function will be slower than loading
        other endpoints.
        Since we're using a generator on the list of branches,
        we can't easily show progress.

        :returns: None
        """
        self._set_collection_date(base_date, window)
        td = base_date - timedelta(days=window)
        td_ts = td.timestamp()
        base_ts = base_date.timestamp()
        starttime = time.time()
        self.log.info("Loading branch details...")
        url = f"/repos/{self.repo_name}/branches"
        self.stats["commits"]["collection_time"] = time.time() - starttime
        for branchdata in self.repo.list_branches():
            branch, last_commit = branchdata
            self.log.debug(f"Processing meta data for {branch}")
            self.stats["branches"]["total_branches"] += 1
            if branch == self.main_branch:
                self.stats["general"]["main_branch_commits"] += 1
            if td_ts < int(last_commit) < base_ts:
                self.stats["branches"]["total_window_branches"] += 1

            """
            Branch author data is harder to suss out from git
            operations alone, so we'll pull that data from the
            api. Along with whether the branch is protected,
            which is _definitely_ not marked in git itself
            """
            url = f"/repos/{self.repo_name}/branches/{branch}"
            try:
                data = [q for q in self._github_query(url)]
                if data:
                    data = data[0]
            except Exception:
                pass
            else:
                if not data or not data["commit"]["commit"]["author"]["name"]:
                    self.stats["branches"]["total_empty_branches"] += 1
                    self.log.debug(
                        f"{branch} is missing branch information. Skipping..."
                    )
                    continue
                # the best we can do (for now) is get the most recent commit time
                updated = data["commit"]["commit"]["author"]["date"]
                dt_updated = datetime.strptime(updated, "%Y-%m-%dT%H:%M:%SZ")
                self.log.debug(f"{branch} updated at {dt_updated}")
                if dt_updated > base_date:
                    self.log.debug(
                        f"Branch {branch} was created in the future. Skipping."
                    )
                    continue
                if data["protected"]:
                    self.stats["branches"]["protected_branches"] += 1
                if data["commit"].get("author", None):
                    author = self._cache_user_login(data["commit"]["author"]["login"])
                    self.stats["users"][author]["total_branches"] += 1
                    # 2020-12-30T03:19:29Z (RFC3339)
                    if dt_updated < base_date and dt_updated > td:
                        self.stats["users"][author]["total_window_branches"] += 1
                        self.log.debug(f"{branch=}: created {dt_updated}")

        self.stats["branches"]["collection_time"] = time.time() - starttime
        self.log.info(
            f"Loaded branch details in {self.stats['branches']['collection_time']} seconds"
        )

    def load_repo_stats(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        This data is already visible in the "Insights" panel of a repo,
        but it's fairly easy to collect, so let's use it

        This is also the dataset that doesn't return data on initial calls,
        so we may need to retry requests in this section

        :returns: None
        """
        self.log.info("Loading Repo Stats (Github Insights)...")
        self._set_collection_date(base_date, window)
        starttime = time.time()

        """
        Weeks (in Github's world) start on Sunday, so we need to convert
        our current day to the most recent Sunday to get weekly stats.
        This matters for things like code frequency, punch card, etc.
        The logic is:
            1. get the isoweekday value: (0-6) of base_date
              * This is essentially a count of the number of days since Sunday
            2. turn that into a timedelta object and subtract it from base_date
            3. Make sure we make the date the beginning of the day on Sunday, rather than some time during the day
               to avoid gaps in collection
        """
        isoday = base_date.isoweekday()
        if isoday < 2:
            # add a week early in the week to avoid missing stats
            isoday += 7
        sunday = (base_date - timedelta(days=isoday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self.log.debug(f"Most recent Sunday is {sunday}")
        """
        Code frequency:
        [
          [
            1302998400,
            1124,
            -435
          ]
        ]
        Basically tuples of (timestamp, additions, deletions)

        filter dates on the week, not the day for this
        """
        self.log.debug("Loading code frequency stats...")
        url = f"/repos/{self.repo_name}/stats/code_frequency"
        for week in self._github_query(url):
            if not week:
                self.log.warning(f"Received empty reply from {url}...")
                continue
            timestamp, additions, deletions = week
            ts_date = datetime.utcfromtimestamp(timestamp)
            if ts_date > base_date or ts_date < sunday:
                self.log.debug(f"{ts_date} outside defined window, skipping")
                continue
            self.log.debug(
                f"Week {ts_date}, Additions: {additions}, Deletions: {deletions}"
            )
            self.stats["repo_stats"]["code_frequency"][str(ts_date)] = {
                "additions": additions,
                "deletions": deletions,
            }

        """
        Commit activity:
        [
          {
            "days": [
              0,
              3,
              26,
              20,
              39,
              1,
              0
            ],
            "total": 89,
            "week": 1336280400
          }
        ]
        A list of each day of the week and the number of commits that day, timestamp is
        that week's Sunday. So each day moves forward

        filter dates on the week, not the day for this
        """
        self.log.debug("Loading commit activity stats...")
        url = f"/repos/{self.repo_name}/stats/commit_activity"
        for week in self._github_query(url):
            if not week:
                self.log.warning(f"Received empty reply from {url}...")
                continue
            week_ts = week["week"]
            ts_date = datetime.utcfromtimestamp(week_ts)
            if ts_date > base_date or ts_date < sunday:
                self.log.debug(f"{ts_date} outside defined window, skipping")
                continue
            self.stats["repo_stats"]["commit_activity"][str(ts_date)] = {
                "daily": dict(),
                "total_commits": week["total"],
            }
            for date_offset in range(0, 7):
                newdate = ts_date + timedelta(date_offset)
                self.stats["repo_stats"]["commit_activity"][str(ts_date)]["daily"][
                    str(newdate)
                ] = week["days"][date_offset]
        """
        Contributors:
        """
        self.log.debug("Loading contributor stats...")
        url = f"/repos/{self.repo_name}/stats/contributors"
        for contributor in self._github_query(url):
            if not contributor:
                self.log.warning(f"Received empty reply from {url}...")
                continue
            user = self._cache_user_login(contributor["author"]["login"])
            self.stats["repo_stats"]["contributors"][user] = {
                "total_commits": contributor["total"],
                "weeks": dict(),
            }
            for week in contributor["weeks"]:
                ts_date = datetime.utcfromtimestamp(week["w"])
                if ts_date > base_date or ts_date < sunday:
                    self.log.debug(
                        f"{ts_date} outside defined window ({sunday} - {base_date}), skipping"
                    )
                    continue
                if week["c"] < 1:
                    self.log.debug(f"{user} had no commits in {ts_date}")
                    continue
                self.stats["repo_stats"]["contributors"][user]["weeks"][
                    str(ts_date)
                ] = {
                    "commits": week["c"],
                    "additions": week["a"],
                    "deletions": week["d"],
                }
            if not self.stats["repo_stats"]["contributors"][user]["weeks"]:
                self.log.debug(f"{user} has no commits within range")
                self.stats["repo_stats"]["contributors"].pop(user, None)
                continue
        """
        TO DO: We should sort the contributor list by number of commits
        to make understanding our noisiest contributors easier
        Remember that noisy != best
        """

        """
        Punch Card:
        [
          [0, 0, 5],
          [0, 1, 43],
          [0, 2, 21]
        ]
        Essentially "tuples" (but JSON doesn't have tuples) of (number referencing day of week, hour, commit count)
        """
        self.log.debug("Loading punch card stats...")
        url = f"/repos/{self.repo_name}/stats/punch_card"
        for hourtuple in self._github_query(url):
            if not hourtuple:
                self.log.warning(f"Received empty reply from {url}")
                continue
            day_no, hour, commits = hourtuple
            day_name = calendar.day_name[day_no]
            self.stats["repo_stats"]["punchcard"]["total_commits"] += commits
            if day_name in self.stats["repo_stats"]["punchcard"]["days"]:
                self.stats["repo_stats"]["punchcard"]["days"][day_name][hour] = commits
                self.stats["repo_stats"]["punchcard"]["days"][day_name][
                    "total_commits"
                ] += commits
                busiest_hour = self.stats["repo_stats"]["punchcard"]["days"][day_name][
                    "busiest_hour"
                ]
                if (
                    commits
                    > self.stats["repo_stats"]["punchcard"]["days"][day_name][
                        busiest_hour
                    ]
                ):
                    self.stats["repo_stats"]["punchcard"]["days"][day_name][
                        "busiest_hour"
                    ] = hour
            else:
                self.stats["repo_stats"]["punchcard"]["days"][day_name] = {
                    hour: commits,
                    "total_commits": commits,
                    "busiest_hour": hour,
                }
        """
        Sort the daily commit stats so we can easily pick out our
        noisiest day.
        Remember that noisy != best
        """
        self.stats["repo_stats"]["punchcard"]["sorted_days"] = sorted(
            [
                (k, v["total_commits"])
                for k, v in self.stats["repo_stats"]["punchcard"]["days"].items()
            ],
            key=lambda k: k[1],
            reverse=True,
        )
        self.stats["repo_stats"]["collection_time"] = time.time() - starttime
        self.log.info(
            f"Loaded repo stats in {self.stats['repo_stats']['collection_time']} seconds"
        )

    def load_releases(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        Get details about releases

        As with PRs, we may want details about older releases, so
        we don't filter the queries on time

        :returns: None
        """
        self.log.info("Loading release details...")
        starttime = time.time()
        td = base_date - timedelta(days=window)
        url = f"/repos/{self.repo_name}/releases"
        for release in self._github_query(url):
            name = release["name"]
            user = self._cache_user_login(release["author"]["login"])
            dt_created = datetime.strptime(release["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            if dt_created > base_date:
                self.log.debug(f"Release {name} was created in the future. Skipping.")
                continue
            if dt_created.date() <= base_date.date() and dt_created.date() >= td.date():
                self.stats["releases"]["total_window_releases"] += 1
                self.stats["users"][user]["total_window_releases"] += 1
            self.stats["releases"]["total_releases"] += 1
            self.stats["releases"]["releases"][name] = {
                "created_at": str(dt_created),
                "author": user,
                "body": release["body"],
            }
            self.stats["users"][user]["total_releases"] += 1
        self.stats["releases"]["collection_time"] = time.time() - starttime
        self.log.info(
            f"Loaded release details in {self.stats['releases']['collection_time']} seconds"
        )

    def load_workflow_runs(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        Parse through workflow runs and collect results

        :returns: None
        """
        self.log.info("Loading workflow details...")
        self._set_collection_date(base_date, window)
        starttime = time.time()
        td = base_date - timedelta(days=window)
        url = f"/repos/{self.repo_name}/actions/runs"
        # only request workflow detail within window
        for run in self._github_query(url, key="workflow_runs"):
            workflow = run["name"]
            status = run["conclusion"]
            # reasons to skip
            if workflow in self.ignored_workflows:
                self.log.debug(f"Skipping {workflow} because we ignore that workflow")
                continue
            if run["status"] in self.ignored_statuses:
                self.log.debug(
                    f"Skipping {run['head_commit']['message']} because we ignore {run['status']}"
                )
                continue
            if not status:
                self.log.debug(f"Empty status for {workflow}...skipping")
                continue
            dt_created = datetime.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            if dt_created > base_date:
                self.log.debug(
                    f"Workflow {workflow} was created in the future. Skipping."
                )
                continue
            try:
                user = self._cache_user_login(run["triggering_actor"]["login"])
            except Exception:
                name = run["head_commit"]["author"]["name"]
                if name in self.broken_users:
                    continue
                user = self._cache_user_name(run["head_commit"]["author"]["name"])
            event = run["event"]
            # Track event stats
            if event in self.stats["workflows"]["events"]:
                self.stats["workflows"]["events"][event]["total"] += 1
            else:
                self.stats["workflows"]["events"][event] = {"total": 1, "window": 0}
            if dt_created > td and dt_created < base_date:
                self.stats["workflows"]["events"][event]["window"] += 1

            # Track user stats
            if event not in self.non_user_events:
                if event in self.stats["users"][user]["events"]:
                    self.stats["users"][user]["events"][event] += 1
                else:
                    self.stats["users"][user]["events"][event] = 1
                if workflow in self.stats["users"][user]["workflows"]:
                    if status in self.stats["users"][user]["workflows"][workflow]:
                        self.stats["users"][user]["workflows"][workflow][status] += 1
                    else:
                        self.stats["users"][user]["workflows"][workflow][status] = 1
                else:
                    self.stats["users"][user]["workflows"][workflow] = {status: 1}

                if status in self.stats["users"][user]["workflow_totals"]:
                    self.stats["users"][user]["workflow_totals"][status] += 1
                else:
                    self.stats["users"][user]["workflow_totals"][status] = 1

            # Track workflow stats
            if workflow in self.stats["workflows"]["workflows"]:
                self.stats["workflows"]["workflows"][workflow]["total_window_runs"] += 1
                if status in self.stats["workflows"]["workflows"][workflow]["runs"]:
                    self.stats["workflows"]["workflows"][workflow]["runs"][status] += 1
                else:
                    self.stats["workflows"]["workflows"][workflow]["runs"][status] = 1
            else:
                self.stats["workflows"]["workflows"][workflow] = {
                    "retries": 0,
                    "last_run": run["run_number"],
                    "total_window_runs": 1,
                    "runs": {status: 1},
                }
            if run["run_attempt"] > 1:
                self.stats["workflows"]["workflows"][workflow]["retries"] += 1
            if (
                run["run_number"]
                > self.stats["workflows"]["workflows"][workflow]["last_run"]
            ):
                self.stats["workflows"]["workflows"][workflow]["last_run"] = run[
                    "run_number"
                ]

        """
        calculate percentage of runs executed in this window

        We have to do this once we've collected all the expected
        workflow data to ensure the math works out correctly
        """
        for workflow, data in self.stats["workflows"]["workflows"].items():
            window_runs = data["total_window_runs"]
            last_run = data["last_run"]
            success = data["runs"].get("success", 0)
            fail = data["runs"].get("failure", 0)
            cancelled = data["runs"].get("cancelled", 0)
            start_fail = data["runs"].get("startup_failure", 0)
            skipped = data["runs"].get("skipped", 0)

            self.stats["workflows"]["workflows"][workflow][
                "window_runs_of_total_percentage"
            ] = round((window_runs / last_run) * 100, 2)
            if success > 0:
                self.stats["workflows"]["workflows"][workflow][
                    "run_success_percentage"
                ] = round((success / window_runs) * 100, 2)
            else:
                self.stats["workflows"]["workflows"][workflow][
                    "run_success_percentage"
                ] = 0
            if fail > 0:
                self.stats["workflows"]["workflows"][workflow][
                    "run_failure_percentage"
                ] = round((fail / window_runs) * 100, 2)
            else:
                self.stats["workflows"]["workflows"][workflow][
                    "run_failure_percentage"
                ] = 0
            if cancelled > 0:
                self.stats["workflows"]["workflows"][workflow][
                    "run_cancelled_percentage"
                ] = round((cancelled / window_runs) * 100, 2)
            else:
                self.stats["workflows"]["workflows"][workflow][
                    "run_cancelled_percentage"
                ] = 0
            if start_fail > 0:
                self.stats["workflows"]["workflows"][workflow][
                    "run_startup_failure_percentage"
                ] = round((start_fail / window_runs) * 100, 2)
            else:
                self.stats["workflows"]["workflows"][workflow][
                    "run_startup_failure_percentage"
                ] = 0
            if skipped > 0:
                self.stats["workflows"]["workflows"][workflow][
                    "run_skipped_percentage"
                ] = round((skipped / window_runs) * 100, 2)
            else:
                self.stats["workflows"]["workflows"][workflow][
                    "run_skipped_percentage"
                ] = 0
        self.stats["workflows"]["collection_time"] = time.time() - starttime
        self.log.info(
            f"Loaded workflow details in {self.stats['workflows']['collection_time']} seconds"
        )
