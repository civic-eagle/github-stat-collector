from datetime import datetime, timedelta
import logging
import os
import pygit2
import time

# local imports
from github_stats.schema import DEFAULT_WINDOW


class Repo(object):
    def __init__(self, config):
        auth_token = os.environ.get("GITHUB_TOKEN", None)
        if not auth_token:
            auth_token = config["repo"].get("github_token", None)
        if not auth_token:
            raise Exception("Cannot find Github auth token in environment or config")
        self.log = logging.getLogger("github-stats.repo-loading")

        self.callbacks = pygit2.RemoteCallbacks(
            pygit2.UserPass("x-access-token", auth_token)
        )
        self.repo_url = config["repo"]["clone_url"]
        self.repo_path = f"{config['repo']['folder']}/{config['repo']['name']}"
        self.repoobj = self._prep_repo()
        self.primary_branches = config["repo"]["branches"]

    def _prep_repo(self):
        if not pygit2.discover_repository(self.repo_path):
            self.log.info(f"Creating {self.repo_path}...")
            pygit2.clone_repository(
                self.repo_url,
                self.repo_path,
                callbacks=self.callbacks,
            )
        self.log.info(f"Updating {self.repo_path}...")
        r = pygit2.Repository(self.repo_path)
        remote = r.remotes["origin"]
        self.log.debug("Fetching remote...")
        progress = remote.fetch(callbacks=self.callbacks)
        while progress.received_objects < progress.total_objects:
            sleep(1)
        self.log.debug("Fast-forwarding...")
        remote_id = r.lookup_reference("refs/remotes/origin/develop").target
        self.log.debug(f"remote id: {remote_id}")
        repo_branch = r.lookup_reference("refs/heads/develop")
        repo_branch.set_target(remote_id)
        r.checkout_tree(r.get(remote_id))
        master_ref = r.lookup_reference("refs/heads/develop")
        master_ref.set_target(remote_id)
        r.head.set_target(remote_id)
        self.log.info(f"{self.repo_path} is up to date")
        return r

    def _checkout_branch(self, branch):
        self.log.debug(f"Checking out {branch}...")
        remote_id = r.lookup_reference(f"refs/remotes/origin/{branch}").target
        self.log.debug(f"remote id: {remote_id}")
        repo_branch = r.lookup_reference(f"refs/heads/{branch}")
        repo_branch.set_target(remote_id)
        r.checkout_tree(r.get(remote_id))
        master_ref = r.lookup_reference(f"refs/heads/{branch}")
        master_ref.set_target(remote_id)
        r.head.set_target(remote_id)

    def list_branches(self):
        # count the two branches we'll otherwise skip
        if self.primary_branches["main"] != self.primary_branches["release"]:
            branch_count = 2
        else:
            branch_count = 1

        self.log.info(f"Checking branches...")
        for branch in self.repoobj.branches:
            branch_name = branch.replace("origin/", "")
            if branch_name in [
                "HEAD",
                self.primary_branches["main"],
                self.primary_branches["release"],
            ]:
                continue
            branch_count += 1
            yield branch_name
        self.log.info(f"Found {branch_count} branches in the repo")

    def commit_log(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        self.log.info("Checking commit log...")
        td = base_date - timedelta(days=window)
        commit_count = 0
        window_commit_count = 0
        for commit in self.repoobj.walk(
            self.repoobj.head.target,
            pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE,
        ):
            commit_count += 1
            # commit objects are C objects, need to convert types
            commitobj = {
                "author": str(commit.author),
                "time": int(commit.commit_time),
                "message": str(commit.message),
            }
            if td.timestamp() < commitobj["time"] < base_date.timestamp():
                window_commit_count += 1
            yield commitobj
        self.log.info(
            f"Found {commit_count} commits, {window_commit_count} of which happened in our window"
        )
