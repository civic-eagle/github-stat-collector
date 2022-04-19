from datetime import datetime, timedelta
import logging
import os
import pygit2
from pygit2 import GIT_SORT_TOPOLOGICAL, GIT_SORT_REVERSE
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
        progress = remote.fetch(callbacks=self.callbacks)
        while progress.received_objects < progress.total_objects:
            sleep(1)
        self.log.info(f"{self.repo_path} is up to date")
        return r

    def commit_log(self, base_date=datetime.today(), window=DEFAULT_WINDOW):
        self.log.info("Collecting commit log...")
        td = base_date - timedelta(days=window)
        commit_count = 0
        window_commit_count = 0
        for commit in self.repoobj.walk(self.repoobj.head.target, GIT_SORT_TOPOLOGICAL | GIT_SORT_REVERSE):
            commit_count += 1
            # commit objects are C objects, need to convert types
            commitobj = {
                    "author": str(commit.author),
                    "time": int(commit.commit_time),
                    "message": str(commit.message),
                    }
            if td.timestamp() < commitobj["time"] < base_date.timestamp():
                window_commit_count += 1
        self.log.info(f"Found {commit_count} commits, {window_commit_count} of which happened in our window")
