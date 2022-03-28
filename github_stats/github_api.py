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
import regex
import time
import urllib.parse

calendar.setfirstweekday(calendar.SUNDAY)
DEFAULT_WINDOW = 7


class GithubAccess(object):
    BASE_URL = "https://api.github.com/"

    def __init__(self, config):
        auth_token = os.environ.get("GITHUB_TOKEN", None)
        if not auth_token:
            auth_token = config.get("auth", {}).get("github_token", None)
            if not auth_token:
                raise Exception(
                    "Cannot find Github auth token in environment or config"
                )

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

        self.repo_name = config["repo"]["name"]
        self.org = config["repo"]["org"]
        self.log = logging.getLogger("github-stats.collection")
        self.ignored_workflows = config["repo"].get("ignored_workflows", list())
        self.ignored_statuses = config["repo"].get("ignored_statuses", ["queued"])
        self.main_branch = config["repo"]["branches"].get("main", "main")
        self.release_branch = config["repo"]["branches"].get("release", "main")
        self.non_user_events = ["schedule"]
        """
        Many tag patterns
        """
        self.tag_matches = {
            tag["name"]: regex.compile(f".*{tag['pattern']}.*")
            for tag in config["repo"].get("tag_patterns", list())
        }
        """
        Many label matching patterns
        """
        self.label_matches = {
            labelname: labels
            for labelname, labels in config["repo"].get("labels", {}).items()
        }

        """
        Defaults for some internal dicts
        """
        self.user_schema = {
            "inactive_branches": list(),
            "total_inactive_branches": 0,
            "total_pull_requests": 0,
            "total_open_pull_requests": 0,
            "open_pull_requests": [],
            "closed_pull_requests": [],
            "total_closed_pull_requests": 0,
            "total_commits": 0,
            "events": dict(),
            "workflows": dict(),
            "workflow_totals": dict(),
            "branches": list(),
            "total_branches": 0,
        }

        self.user_login_cache = {
            "names": dict(),
            "logins": dict(),
        }

        """
        Actual stats object
        """
        self.stats = {
            "collection_date": None,
            "repo_stats": {
                "code_frequency": dict(),
                "commit_activity": dict(),
                "contributors": dict(),
                "punchcard": {
                    "total_commits": 0,
                    "sorted_days": list(),
                    "days": dict(),
                },
            },
            # "code_scanning": {
            #     "open": dict(),
            #     "closed": dict(),
            #     "dismissed": dict(),
            # },
            "branches": {
                "branches": dict(),
                "inactive_branches": dict(),
                "total_branches": 0,
                "total_active_branches": 0,
                "total_inactive_branches": 0,
                "protected_branches": 0,
                "total_empty_branches": 0,
                "empty_branches": list(),
            },
            "workflows": {"events": dict(), "workflows": dict()},
            "pull_requests": {
                "total_pull_requests": 0,
                "total_open_pull_requests": 0,
                "total_closed_pull_requests": 0,
                "total_active_pull_requests": 0,
                "total_inactive_pull_requests": 0,
                "total_draft_pull_requests": 0,
                "open_pull_requests": list(),
                "closed_pull_requests": list(),
                "labels": {
                    label: {
                        "total_recent_prs": 0,
                        "total_old_prs": 0,
                        "total_prs": 0,
                        "pulls": [],
                    }
                    for label in self.label_matches
                },
            },
            "users": dict(),
            "releases": {
                "total_releases": 0,
                "releases": dict(),
            },
            "commits": {"branch_commits": dict(), "total_commits": 0},
            "general": {
                "main_branch_commits": 0,
                "tag_matches": {
                    t["name"]: 0 for t in config["repo"].get("tag_patterns", list())
                },
            },
        }
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

    def _github_query(self, url, key=None, params={}):
        """
        Query paginated endpoint from Github

        We'll make a generator here to reduce memory pressure
        and allow for faster results processing
        """
        self.log.debug(f"Combining {self.BASE_URL} and {url}")
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
        self.user_login_cache["logins"][login] = name
        self.user_login_cache["names"][name] = login
        if name not in self.stats["users"]:
            self.stats["users"][name] = deepcopy(self.user_schema)
        self.log.debug(f"Returned name: {self.user_login_cache['logins'][login]}")
        return self.user_login_cache["logins"][login]

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
        self.log.info(f"Loaded contributors in {time.time() - starttime} seconds")

    def _process_labels(self, title, labels, key):
        """
        Because this for loop is a bit nasty, and we need to run it
        for both recent and older matching prs, we break it out of
        the actual load_pull_requests() function

        :returns: None
        """
        for label in labels:
            name = label["name"]
            for labelname, matches in self.label_matches.items():
                if name not in matches:
                    continue
                self.log.debug(f"{title}: {name} ({matches=}) for {label}")
                self.stats["pull_requests"]["labels"][labelname]["total_prs"] += 1
                self.stats["pull_requests"]["labels"][labelname][key] += 1
                self.stats["pull_requests"]["labels"][labelname]["pulls"].append(title)

    def _set_collection_date(self, date):
        if not self.stats["collection_date"]:
            self.stats["collection_date"] = date
            self.log.debug(f"Collection timestamp: {date}")

    def load_all_stats(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        Wrapper to execute all stat collection functions

        :returns: None
        """
        self._set_collection_date(base_date)
        self.load_repo_stats(base_date, window)
        self.load_pull_requests(base_date, window)
        self.load_branches(base_date, window)
        self.load_releases(base_date, window)
        self.load_workflow_runs(base_date, window)

    def load_pull_requests(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        Collect pull request data

        Because we want to see older pull requests as well, we don't
        filter the initial query based on time here

        :returns: None
        """
        self._set_collection_date(base_date)
        td = base_date - timedelta(days=window)
        starttime = time.time()
        self.log.info("Loading Pull Request Data...")
        url = f"/repos/{self.repo_name}/pulls"
        for pull in self._github_query(url, params={"state": "all"}):
            self.stats["pull_requests"]["total_pull_requests"] += 1
            if pull["draft"]:
                self.stats["pull_requests"]["total_draft_pull_requests"] += 1
            modified_time = datetime.strptime(pull["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
            if (
                modified_time.date() > base_date.date()
                or modified_time.date() < td.date()
            ):
                self.stats["pull_requests"]["total_inactive_pull_requests"] += 1
                self._process_labels(pull["title"], pull["labels"], "total_old_prs")
            else:
                self.stats["pull_requests"]["total_active_pull_requests"] += 1
                self._process_labels(pull["title"], pull["labels"], "total_recent_prs")
            author = self._cache_user_login(pull["user"]["login"])
            self.stats["users"][author]["total_pull_requests"] += 1
            """
            We'll be explicit about state here to avoid
            changed state values affecting this later
            """
            if pull["state"] == "open":
                self.stats["pull_requests"]["total_open_pull_requests"] += 1
                self.stats["users"][author]["total_open_pull_requests"] += 1
                self.stats["users"][author]["open_pull_requests"].append(pull["title"])
                self.stats["pull_requests"]["open_pull_requests"].append(pull["title"])
            elif pull["state"] == "closed":
                self.stats["pull_requests"]["total_closed_pull_requests"] += 1
                self.stats["users"][author]["total_closed_pull_requests"] += 1
                self.stats["users"][author]["closed_pull_requests"].append(
                    pull["title"]
                )
                self.stats["pull_requests"]["closed_pull_requests"].append(
                    pull["title"]
                )
        self.log.info(f"Loaded pull requests in {time.time() - starttime} seconds")

    def load_branches(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        Because getting branch details requires a second
        query, this function will be slower than loading
        other endpoints.
        Since we're using a generator on the list of branches,
        we can't easily show progress.

        :returns: None
        """
        self._set_collection_date(base_date)
        td = base_date - timedelta(days=window)
        starttime = time.time()
        self.log.info("Loading branch details...")
        url = f"/repos/{self.repo_name}/branches"
        for branch in self._github_query(url):
            self.stats["branches"]["total_branches"] += 1
            if branch["protected"]:
                self.stats["branches"]["protected_branches"] += 1
            name = branch["name"]
            url = f"/repos/{self.repo_name}/branches/{name}"
            # because we return generators...but there's only one branch requested
            data = [q for q in self._github_query(url)]
            if data:
                data = data[0]
            if not data or not data["commit"]["commit"]["author"]["name"]:
                self.stats["branches"]["total_empty_branches"] += 1
                self.stats["branches"]["empty_branches"].append(name)
                self.log.debug(f"{name} is missing branch information. Skipping...")
                continue
            created = data["commit"]["commit"]["author"]["date"]
            if data["commit"].get("author", None):
                author = self._cache_user_login(data["commit"]["author"]["login"])
            else:
                """
                Some commits (typically older ones) don't have author data
                """
                author = data["commit"]["commit"]["author"]["name"]
                if author not in self.stats["users"]:
                    self.log.debug(
                        f"Creating new user {author} for this branch {name=}"
                    )
                    self.stats["users"][author] = deepcopy(self.user_schema)
                    self.user_login_cache["names"][author] = author
                    self.user_login_cache["logins"][author] = author
            self.stats["users"][author]["total_branches"] += 1
            # 2020-12-30T03:19:29Z (RFC3339)
            dt_created = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ")
            if dt_created.date() > base_date.date() or dt_created.date() < td.date():
                self.stats["users"][author]["total_inactive_branches"] += 1
                self.stats["users"][author]["inactive_branches"].append(name)
                self.log.debug(
                    f"Branch {name}: created {dt_created}, outside window {td} - {base_date}"
                )
                self.stats["branches"]["inactive_branches"][name] = {
                    "commit": data["commit"]["sha"],
                    "author": author,
                    "created": data["commit"]["commit"]["author"]["date"],
                }
                self.stats["branches"]["total_inactive_branches"] += 1
            else:
                self.stats["users"][author]["branches"].append(name)
                self.stats["branches"]["branches"][name] = {
                    "commit": data["commit"]["sha"],
                    "author": author,
                    "created": data["commit"]["commit"]["author"]["date"],
                }
                self.stats["branches"]["total_active_branches"] += 1
                self.log.debug(f"Branch {name}: created {dt_created}")
        self.log.info(f"Loaded branch details in {time.time() - starttime} seconds")

    def load_repo_stats(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        This data is already visible in the "Insights" panel of a repo,
        but it's fairly easy to collect, so let's use it

        This is also the dataset that doesn't return data on initial calls,
        so we may need to retry requests in this section

        :returns: None
        """
        self.log.info("Loading Repo Stats (Github Insights)...")
        self._set_collection_date(base_date)
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
        self.log.info(f"Loaded repo stats in {time.time() - starttime} seconds")

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
            dt_created = datetime.strptime(release["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            if dt_created.date() > base_date.date() or dt_created.date() < td.date():
                self.log.debug(f"{name} outside window, skipping")
                continue
            self.stats["releases"]["total_releases"] += 1
            self.stats["releases"]["releases"][name] = {
                "created_at": str(dt_created),
                "author": self._cache_user_login(release["author"]["login"]),
                "body": release["body"],
            }
        self.log.info(f"Loaded release details in {time.time() - starttime} seconds")

    def load_code_scanning(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        Pull results from dependabot scans
        Requires specific permissions

        :returns: None
        """
        self.log.info("Loading Dependabot details...")
        self._set_collection_date(base_date)
        # url = f"/repos/{self.repo_name}/code-scanning/alerts"

    def load_workflow_runs(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        Parse through workflow runs and collect results

        :returns: None
        """
        self.log.info("Loading workflow details...")
        self._set_collection_date(base_date)
        starttime = time.time()
        td = base_date - timedelta(days=window)
        url = f"/repos/{self.repo_name}/actions/runs"
        # only request workflow detail within window
        params = {"created": f">={td.date()}"}
        for run in self._github_query(url, key="workflow_runs", params=params):
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

            user = self._cache_user_login(run["triggering_actor"]["login"])
            event = run["event"]
            # Track event stats
            if event in self.stats["workflows"]["events"]:
                self.stats["workflows"]["events"][event] += 1
            else:
                self.stats["workflows"]["events"][event] = 1

            # Track user stats
            if event not in self.non_user_events:
                self.stats["users"][user]["total_commits"] += 1
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
                if user not in self.stats["workflows"]["workflows"][workflow]["users"]:
                    self.stats["workflows"]["workflows"][workflow]["users"].append(user)
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
                    "users": [user],
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

            # Track general commit data
            branch = run["head_branch"]
            if not branch:
                self.log.debug(f"Empty branch name for: {pprint.pformat(run)}")
            else:
                self.stats["commits"]["total_commits"] += 1
                if branch in self.stats["commits"]["branch_commits"]:
                    self.stats["commits"]["branch_commits"][branch] += 1
                else:
                    self.stats["commits"]["branch_commits"][branch] = 1
                # Track tag matching branches
                for name, pattern in self.tag_matches.items():
                    self.log.debug(
                        f"Attempting to match {name} :: {pattern} to {branch}"
                    )
                    if pattern.match(branch):
                        self.stats["general"]["tag_matches"][name] += 1
            if branch == self.main_branch:
                self.stats["general"]["main_branch_commits"] += 1

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
        self.log.info(f"Loaded workflow details in {time.time() - starttime} seconds")
