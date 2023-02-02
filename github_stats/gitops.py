from datetime import datetime, timedelta
import logging
import os
import pygit2
import time

from github_stats.util import load_patterns
from github_stats.schema import DEFAULT_WINDOW


class Repo(object):
    def __init__(self, config):
        self.log = logging.getLogger("github-stats.repo")
        auth_token = os.environ.get("GITHUB_TOKEN", None)
        if not auth_token:
            auth_token = config["repo"].get("github_token", None)
        self.callbacks = None
        if auth_token:
            self.callbacks = pygit2.RemoteCallbacks(
                pygit2.UserPass("x-access-token", auth_token)
            )
        if "clone_url" in config["repo"]:
            self.repo_url = config["repo"]["clone_url"]
        else:
            self.repo_url = (
                f"https://github.com/{config['repo']['org']}/{config['repo']['name']}"
            )
        self.repo_path = f"{config['repo']['folder']}/{config['repo']['name']}"
        self.primary_branches = config["repo"]["branches"]
        self.tag_matches, self.bug_matches, _ = load_patterns(
            config["repo"].get("tag_patterns", []),
            config["repo"].get("bug_matching", {}),
        )
        self._prep_repo()
        if config["repo"].get("tagged_releases", False):
            self._get_releases(tags=True)
        else:
            self._get_releases(branch=True)

    def _prep_repo(self):
        """
        Clone repo if it doesn't exist
        and otherwise update the main repo to current

        :returns: None
        """
        if not pygit2.discover_repository(self.repo_path):
            self.log.info(f"Creating {self.repo_path}...")
            pygit2.clone_repository(
                self.repo_url,
                self.repo_path,
                callbacks=self.callbacks,
            )
        self.log.info(f"Updating {self.repo_path}...")
        self.repoobj = pygit2.Repository(self.repo_path)
        remote = self.repoobj.remotes["origin"]
        progress = remote.fetch(callbacks=self.callbacks)
        # pulling data from repo is async, so we have to wait here
        while progress.received_objects < progress.total_objects:
            time.sleep(1)
        self.main_branch_id = self._checkout_branch(
            self.primary_branches["main"]
        ).target

    def _get_releases(self, branch=False, tag=False):
        """
        find all matching releases
        and convert them to their corresponding commit objects
        This let's us do an OID comparison between each commit
        and the tag references
        """
        self.releases = []
        if tag:
            for r in self.repoobj.references:
                self.log.debug(
                    f"Checking reference {r}, {self.repoobj.references[r].type} for tag matching"
                )
                # use this to short-circuit larger reference lists
                if (
                    "tag" in r
                    and self.repoobj.references[r].type == pygit2.GIT_REF_OID
                    and any(v.match(r) for v in self.tag_matches.values())
                ):
                    target = self.repoobj[self.repoobj.references[r].target]
                    if target.type == pygit2.GIT_OBJ_TAG:
                        target = self.repoobj[target.target]
                    self.releases.append(
                        (
                            str(target.hex),
                            int(target.commit_time),
                            str(target.author),
                        )
                    )
        elif branch:
            for commit in self.branch_commit_log(self.primary_branches["release"]):
                self.releases.append(
                    (
                        commit["hash"],
                        commit["time"],
                        commit["author"],
                    )
                )

        # sort by commit timestamp
        self.releases.sort(key=lambda x: x[1])

    def _checkout_branch(self, branch):
        """
        Checkout a particular branch
        and return the tracking object

        :returns: branch object
        :rtype: pygit2.Reference
        """
        self.log.debug(f"Checking out {branch}...")
        remote_id = self.repoobj.lookup_reference(f"refs/remotes/origin/{branch}")
        self.repoobj.checkout(remote_id, strategy=pygit2.GIT_CHECKOUT_ALLOW_CONFLICTS)
        return remote_id

    def list_branches(self):
        """
        Generator that discovers all branches in the repo

        :returns: tuple of branch name and initial commit time
        """
        # count the two branches we'll otherwise skip
        if self.primary_branches["main"] != self.primary_branches["release"]:
            branch_count = 2
        else:
            branch_count = 1

        self.log.debug("listing branches...")
        for branch in list(
            set([self.primary_branches["main"], self.primary_branches["release"]])
        ):
            remote_id = self.repoobj.lookup_reference(
                f"refs/remotes/origin/{branch}"
            ).target
            commit = self.repoobj.get(remote_id)
            yield (branch, commit.commit_time)
        for branch in self.repoobj.branches:
            branch_name = branch.replace("origin/", "")
            # skip specific branch names in our count
            if branch_name in [
                "HEAD",
                self.primary_branches["main"],
                self.primary_branches["release"],
            ]:
                continue
            branch_count += 1
            # look up the branch to get the last commit time
            remote_id = self.repoobj.lookup_reference(
                f"refs/remotes/origin/{branch_name}"
            ).target
            commit = self.repoobj.get(remote_id)
            yield (branch_name, commit.commit_time)
        self.log.debug(f"Found {branch_count} branches in the repo")

    def tag_releases(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        """
        :returns: total count of releases, windowed releases
        """
        release_stats = {
            "total_releases": 0,
            "users": dict(),
            "total_window_releases": 0,
        }
        window_end_ts = base_date.timestamp()
        window_start_ts = (base_date - timedelta(window)).timestamp()
        for release in self.releases:
            user = release[2]
            release_stats["total_releases"] += 1
            if user in release_stats["users"]:
                release_stats["users"][user]["total_releases"] += 1
            else:
                release_stats["users"][user] = {
                    "total_window_releases": 0,
                    "total_releases": 1,
                }
            # because we check for the user above this if statement, we don't have to check again inside it
            if window_start_ts < release[1] < window_end_ts:
                release_stats["total_window_releases"] += 1
                release_stats["users"][user]["total_window_releases"] += 1
        self.log.debug(f"{release_stats=}")
        return release_stats

    def match_bugfixes(
        self, pr_list, base_date=datetime.today(), window=DEFAULT_WINDOW
    ):
        """
        Given a list of PRs merge commits, find the matching releases

        A "matching" release in this case is the nearest release in the
        commit log that is newer than the commit itself

        :returns: rough mttr, rough windowed mttr
        :rtype: float
        """
        if not self.releases or not pr_list:
            return 0, 0
        window_end_ts = base_date.timestamp()
        window_start_ts = (base_date - timedelta(window)).timestamp()
        windowed_mttr = 0
        windowed_releases = list()
        mttr = 0
        self.log.debug("Tracking MTTR...")
        for pr in pr_list:
            for release in self.releases:
                # if timestamp is greater than release timestamp, then this belongs to a newer release
                if pr[2] > release[1]:
                    continue
                elif pr[2] <= release[1]:
                    self.log.debug(f"{pr[0]} ({pr[1]}) belongs to {release}")
                    # diff between the release time and the commit time
                    release_time = release[1] - pr[2]
                    mttr += release_time
                    """
                    add this release to windowed releases
                    don't worry about duplicates because we can
                    filter them afterwards
                    """
                    if window_start_ts < release[1] < window_end_ts:
                        windowed_releases.append(release[0])
                        windowed_mttr += release_time
                    break
        mttr = mttr / len(pr_list)
        if windowed_releases:
            # ensure no duplicate releases are counted here
            windowed_releases = list(set(windowed_releases))
            windowed_mttr = windowed_mttr / len(windowed_releases)
        else:
            windowed_mttr = 0
        self.log.debug(f"{mttr=}, {windowed_mttr=}")
        return mttr, windowed_mttr

    def commit_release_matching(
        self, base_date=datetime.today(), window=DEFAULT_WINDOW
    ):
        """
        1. Loop through a sorted list of all commits to the repo
        2. find the nearest tagged release to each individual commit
        3. diff the time between the commit and the release
        4. do a rolling average on number of releases

        :returns: Avg commit time, avg windowed commit time, count of unreleased commits, count of all commits
        :rtype: tuple(int, int, int, int)
        """
        window_end_ts = base_date.timestamp()
        window_start_ts = (base_date - timedelta(window)).timestamp()
        avg_commit_time = 0
        unreleased_commits = 0
        commits = 0
        windowed_releases = list()
        windowed_commit_time = 0
        walker = self.repoobj.walk(
            self.main_branch_id, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
        for commit in walker:
            timestamp = int(commit.commit_time)
            commit_hex = str(commit.hex)
            commits += 1

            # short-circuit evaluation if we're missing releases
            if not self.releases:
                continue
            # skip super old timestamps that have bad tags/etc.
            if timestamp < self.releases[0][1]:
                continue
            for release in self.releases:
                # if timestamp is greater than release timestamp, then this belongs to a newer release
                if timestamp > release[1]:
                    continue
                elif commit_hex == release[0]:
                    self.log.debug(f"{commit_hex} matches {release}, skipping")
                    break
                elif timestamp <= release[1]:
                    self.log.debug(f"{commit_hex} belongs to {release}")
                    # diff between the release time and the commit time
                    release_time = release[1] - timestamp
                    avg_commit_time += release_time
                    if window_start_ts < release[1] < window_end_ts:
                        windowed_releases.append(release[0])
                        windowed_commit_time += release_time
                    break
            else:
                self.log.debug(f"No release found for {commit_hex}")
                unreleased_commits += 1

        if self.releases:
            # add one additional release to address commits before the initial release that we skip
            avg_commit_time = avg_commit_time / (len(self.releases) + 1)
            if windowed_releases:
                # ensure no duplicate releases are counted here
                windowed_releases = list(set(windowed_releases))
                windowed_commit_time = windowed_commit_time / len(windowed_releases)
            else:
                # no releases in our window
                windowed_commit_time = 0
            self.log.debug(
                f"{avg_commit_time=}, {windowed_commit_time=}, {unreleased_commits=}, {commits=}"
            )
            return avg_commit_time, windowed_commit_time, unreleased_commits, commits
        else:
            return 0, 0, commits, commits

    def commits_between_releases(self, release1, release2):
        """
        commit_times_output = subprocess.check_output(
            [
                "git",
                "log",
                "--format=%cI",
                f"{release['tag_name']}...{last_release['tag_name']}",
            ],
            cwd=f"{SCRIPTDIR}/repos/{repo['name']}",
        ).decode()
        commit_times_split = commit_times_output.split("\n")
        commit_times = [
            i for i in commit_times_split if i
        ]  # eliminate empty strings
        """
        walker = self.repoobj.walk(release1[0], pygit2.GIT_SORT_TIME)
        commits = []
        for commit in walker:
            self.log.info(
                f"Commit {commit.hex} between {release1[0]}:{release1[1]} and {release2[0]}:{release2[1]}"
            )
            if commit.commit_time > release2[1]:
                self.log.debug("Found commit more recent that last release time")
                break
            commits.append(commit)
        return commits

    def branch_commit_log(self, branch_name):
        """
        Track all commits on a particular branch
        This doesn't work perfectly as merged branches
        are tougher to properly track

        :returns: generator of commit objects for a branch
        :rtype: generator(dict())
        """
        self.log.debug(f"Loading commit log for {branch_name}...")
        commit_count = 0
        """
        To make sure we get the right commit count/etc., we should always
        work with the upstream branches, not local checkouts
        """
        if not branch_name.startswith("origin/"):
            branch = self.repoobj.branches.get(f"origin/{branch_name}")
        else:
            branch = self.repoobj.branches.get(branch_name)
        latest_commit_id = branch.target
        try:
            walker = self.repoobj.walk(latest_commit_id, pygit2.GIT_SORT_TIME)
        except ValueError:
            pass
        else:
            self.log.debug(f"{branch_name=}, {latest_commit_id=}")
            """
            using this on a branch should only return commits to that branch
            There may be _some_ overlap, but we'll be close
            """
            if branch_name != self.primary_branches["main"]:
                walker.hide(self.main_branch_id)
            for commit in walker:
                commit_count += 1
                # commit objects are C objects, need to convert types
                commitobj = {
                    "hash": str(commit.hex),
                    "author": str(commit.author),
                    "time": int(commit.commit_time),
                    "branch": branch_name,
                }
                # self.log.info(f"Obj: {commitobj}, Parents: {commit.parents}")
                # self.log.info(pprint.pformat(commitobj))
                yield commitobj
            self.log.debug(f"Found {commit_count=} in {branch_name}")
