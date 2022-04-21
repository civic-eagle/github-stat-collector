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
        _ = self._checkout_branch(self.primary_branches["main"])

    def _checkout_branch(self, branch):
        self.log.debug(f"Checking out {branch}...")
        self.log.debug("pulling upstream...")
        remote_id = self.repoobj.lookup_reference(f"refs/remotes/origin/{branch}")
        self.repoobj.checkout(remote_id, strategy=pygit2.GIT_CHECKOUT_ALLOW_CONFLICTS)
        return remote_id

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
        self.log.info(f"Found {branch_count} branches in the repo")

    def branch_commit_log(self, branch_name):
        self.log.debug("Loading commit log...")
        main_branch_id = self._checkout_branch(self.primary_branches["main"]).target
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
                walker.hide(main_branch_id)
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
            self.log.debug(f"Found {commit_count} in {branch_name}")
