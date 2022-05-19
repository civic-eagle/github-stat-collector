import logging
import os
import pygit2
import time

from github_stats.util import load_patterns


class Repo(object):
    def __init__(self, config):
        self.log = logging.getLogger("github-stats.repo")
        auth_token = os.environ.get("GITHUB_TOKEN", None)
        if not auth_token:
            auth_token = config["repo"].get("github_token", None)
        if not auth_token:
            raise Exception("Cannot find Github auth token in environment or config")

        self.callbacks = pygit2.RemoteCallbacks(
            pygit2.UserPass("x-access-token", auth_token)
        )
        self.repo_url = config["repo"]["clone_url"]
        self.repo_path = f"{config['repo']['folder']}/{config['repo']['name']}"
        self.primary_branches = config["repo"]["branches"]
        self.tag_matches, self.bug_matches, _ = load_patterns(
            config["repo"].get("tag_patterns", []),
            config["repo"].get("bug_matching", {}),
        )
        self._prep_repo()

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
        while progress.received_objects < progress.total_objects:
            time.sleep(1)
        self.main_branch_id = self._checkout_branch(
            self.primary_branches["main"]
        ).target

    def _checkout_branch(self, branch):
        """
        Checkout a particular branch
        and return the tracking object

        :returns: branch object
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
            if branch_name in [
                "HEAD",
                self.primary_branches["main"],
                self.primary_branches["release"],
            ]:
                continue
            branch_count += 1
            remote_id = self.repoobj.lookup_reference(
                f"refs/remotes/origin/{branch_name}"
            ).target
            commit = self.repoobj.get(remote_id)
            yield (branch_name, commit.commit_time)
        self.log.debug(f"Found {branch_count} branches in the repo")

    def match_bugfixes(self, pr_list):
        """
        Given a list of PRs, find the matching releases

        :returns: rough mttr
        """
        tag_matches = [
            (
                str(self.repoobj[self.repoobj.references[r].target].hex),
                int(self.repoobj[self.repoobj.references[r].target].commit_time),
            )
            for r in self.repoobj.references
            if any(v.match(r) for v in self.tag_matches.values())
            and self.repoobj.references[r].type == pygit2.GIT_REF_OID
        ]
        walker = self.repoobj.walk(
            self.main_branch_id, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
        mttr = 0
        for pr in pr_list:
            walker.reset()
            walker.push(pr[1])
            for commit in walker:
                timestamp = int(commit.commit_time)
                commit_hex = str(commit.hex)
                for release in tag_matches:
                    if commit_hex == release[0]:
                        self.log.debug(f"{commit_hex} matches {release}, skipping")
                        break
                    elif timestamp <= release[1]:
                        self.log.debug(f"{commit_hex} belongs to {release}")
                        # diff between the release time and the commit time
                        mttr += release[1] - pr[2]
                        break
                    # if timestamp is greater than release timestamp, then this belongs to a newer release
                    elif timestamp > release[1]:
                        continue
        mttr = mttr / len(pr_list)
        return mttr

    def commit_release_matching(self):
        """
        1. Loop through a sorted list of all commits to the repo
        2. find the nearest tagged release to each individual commit
        3. diff the time between the commit and the release
        4. do a rolling average on number of releases

        :returns: Avg commit time, count of unreleased commits, count of all commits
        :rtype: tuple(int, int, int)
        """
        avg_commit_time = 0
        unreleased_commits = 0
        commits = 0
        """
        find all matching tags
        and convert them to their corresponding commit objects
        This let's us do an OID comparison between each commit
        and the tag references
        """
        tag_matches = [
            (
                str(self.repoobj[self.repoobj.references[r].target].hex),
                int(self.repoobj[self.repoobj.references[r].target].commit_time),
            )
            for r in self.repoobj.references
            if any(v.match(r) for v in self.tag_matches.values())
            and self.repoobj.references[r].type == pygit2.GIT_REF_OID
        ]
        # sort by commit timestamp
        tag_matches.sort(key=lambda x: x[1])
        walker = self.repoobj.walk(
            self.main_branch_id, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
        for commit in walker:
            timestamp = int(commit.commit_time)
            commit_hex = str(commit.hex)
            commits += 1
            # skip super old timestamps that have bad tags/etc.
            if timestamp < tag_matches[0][1]:
                continue
            for release in tag_matches:
                if commit_hex == release[0]:
                    self.log.debug(f"{commit_hex} matches {release}, skipping")
                    break
                elif timestamp > release[1]:
                    continue
                elif timestamp <= release[1]:
                    self.log.debug(f"{commit_hex} belongs to {release}")
                    # diff between the release time and the commit time
                    avg_commit_time += release[1] - timestamp
                    break
            else:
                self.log.debug(f"No release found for {commit_hex}")
                unreleased_commits += 1
        avg_commit_time = avg_commit_time / len(tag_matches)
        self.log.debug(f"{avg_commit_time=}, {unreleased_commits=}, {commits=}")
        return avg_commit_time, unreleased_commits, commits

    def branch_commit_log(self, branch_name):
        """
        Track all commits on a particular branch
        This doesn't work perfectly as merged branches
        are tougher to properly track

        :returns: generator of commit objects for a branch
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
