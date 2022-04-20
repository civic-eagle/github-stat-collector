import logging
import os
import pygit2
import time


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
        self.primary_branches = config["repo"]["branches"]
        self._prep_repo()

    def _prep_repo(self):
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
        self._checkout_branch(self.primary_branches["main"])

    def _checkout_branch(self, branch):
        self.log.debug(f"Checking out {branch}...")
        self.log.debug("pulling upstream...")
        remote_id = self.repoobj.lookup_reference(f"refs/remotes/origin/{branch}")
        self.repoobj.checkout(remote_id, strategy=pygit2.GIT_CHECKOUT_ALLOW_CONFLICTS)

    def list_branches(self):
        # count the two branches we'll otherwise skip
        if self.primary_branches["main"] != self.primary_branches["release"]:
            branch_count = 2
        else:
            branch_count = 1

        self.log.debug("listing branches...")
        for branch in list(
            set([self.primary_branches["main"], self.primary_branches["release"]])
        ):
            yield branch
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
        self.log.debug(f"Found {branch_count} branches in the repo")

    def _get_branch_ids(self):
        for branch_name in list(self.repoobj.branches.remote):
            branch = self.repoobj.branches.get(branch_name)
            latest_commit_id = branch.target
            yield (branch_name, latest_commit_id)

    def collect_commit_log(self):
        self.log.debug("Loading commit log...")
        self._checkout_branch(self.primary_branches["main"])
        for branch_name in self.list_branches():
            commit_count = 0
            self.log.info(f"Collecting from branch {branch_name}")
            branch = self.repoobj.branches.get(f"origin/{branch_name}")
            latest_commit_id = branch.target
            walker = self.repoobj.walk(latest_commit_id, pygit2.GIT_SORT_REVERSE)
            """
            using this on a branch should only return commits to that branch
            Unfortunately, it does not
            """
            walker.simplify_first_parent()
            for commit in walker:
                commit_count += 1
                # commit objects are C objects, need to convert types
                commitobj = {
                    "hash": str(commit.hex),
                    "author": str(commit.author),
                    "time": int(commit.commit_time),
                    "message": str(commit.message),
                    "branch": branch_name,
                }
                self.log.info(f"Obj: {commitobj}, Parents: {commit.parents}")
                # self.log.info(pprint.pformat(commitobj))
                # yield commitobj
            self.log.info(f"Found {commit_count} in {branch_name}")
