from datetime import datetime
import logging
import regex
from typing import Optional, Tuple

from github_stats.schema import User, Stats, Metric
import yaml

utillog = logging.getLogger("github-stats.util")


def load_patterns(
    tag_patterns: Optional[list] = None, bug_patterns: Optional[dict] = None
) -> Tuple[dict, list, list]:
    """
    compile and format regex pattern matching
    """
    tag_matches = {tag["name"]: regex.compile(tag["pattern"]) for tag in tag_patterns}

    bug_matches = [regex.compile(p) for p in bug_patterns.get("patterns", [])]
    pr_matches = [label for label in bug_patterns.get("labels", [])]
    utillog.debug(f"{tag_matches=}, {bug_matches=}, {pr_matches=}")
    return tag_matches, bug_matches, pr_matches


def load_stats(date: datetime, window: int) -> Stats:
    """
    Define loading of stats object in one place
    (largely to keep the actual api file clean)
    """
    return Stats(
        avg_commit_time_secs=Metric(
            value=0,
            name="avg_commit_time_secs",
            description="The overall average time between commit and release",
            type="gauge",
        ),
        avg_pr_time_open_secs=Metric(
            value=0,
            name="avg_pr_time_open_secs",
            description="The overall average time a PR is open",
            type="gauge",
        ),
        branches_collection_time_secs=Metric(
            value=0,
            name="branches_collection_time_secs",
            description="Time taken collecting branch information",
            type="gauge",
        ),
        # branch_commits
        branches_total=Metric(
            value=0,
            name="branches_total",
            description="Total number of branches in repo",
            type="counter",
        ),
        closed_pull_requests_total=Metric(
            value=0,
            name="closed_pull_requests_total",
            description="All closed pull requests discovered in repo",
            type="counter",
        ),
        code_frequency=dict(),
        collection_date=date,
        # commit_activity
        commits_collection_time_secs=Metric(
            value=0,
            name="commits_collection_time_secs",
            description="Time taken collecting commit information",
            type="gauge",
        ),
        commits_total=Metric(
            value=0,
            name="commits_total",
            description="All commits made in the repo",
            type="counter",
        ),
        commits_window=Metric(
            value=0,
            name="window_commits_total",
            description="All commits made in the repo in our collection window",
            type="gauge",
        ),
        contributor_collection_time_secs=Metric(
            value=0,
            name="contributor_collection_time_secs",
            description="Time taken collecting contributor information",
            type="gauge",
        ),
        # contributors
        draft_pull_requests_total=Metric(
            value=0,
            name="draft_pull_requests_total",
            description="All draft pull requests discovered in repo",
            type="counter",
        ),
        empty_branches_total=Metric(
            value=0,
            name="empty_branches_total",
            description="All branches with no data in them",
            type="counter",
        ),
        main_branch_commits_total=Metric(
            value=0,
            name="main_branch-commits_total",
            description="All commits to the main branch",
            type="counter",
        ),
        merged_pull_requests_total=Metric(
            value=0,
            name="merged_pull_requests_total",
            description="All merged pull requests discovered in repo",
            type="counter",
        ),
        mttr_secs=Metric(
            value=0,
            name="mttr_secs",
            description="Avg time from bug testing to release",
            type="gauge",
        ),
        open_pull_requests_total=Metric(
            value=0,
            name="open_pull_requests_total",
            description="All open pull requests discovered in repo",
            type="counter",
        ),
        pull_requests_total=Metric(
            value=0,
            name="pull_requests_total",
            description="All pull requests discovered in repo",
            type="counter",
        ),
        pr_collection_time_secs=Metric(
            value=0,
            name="pr_collection_time_secs",
            description="Time taken collecting PR information",
            type="gauge",
        ),
        # pr_labels
        pr_time_open_secs_total=Metric(
            value=0,
            name="pr_time_open_secs_total",
            description="Total time PRs are open",
            type="counter",
        ),
        protected_branches_total=Metric(
            value=0,
            name="protected_branches_total",
            description="Count of protected branches in repo",
            type="gauge",
        ),
        release_collection_time_secs=Metric(
            value=0,
            name="release_collection_time_secs",
            description="Time taken collecting release information",
            type="gauge",
        ),
        releases_total=Metric(
            value=0,
            name="releases_total",
            description="Count of releases made in repo",
            type="counter",
        ),
        # tag_matches
        total_collection_time_secs=Metric(
            value=0,
            name="total_collection_time_secs",
            description="Time taken collecting all information for the repo",
            type="gauge",
        ),
        unreleased_commits_total=Metric(
            value=0,
            name="unreleased_commits_total",
            description="Count of commits that aren't associated with a release",
            type="gauge",
        ),
        # users
        window=window,
        window_branches_total=Metric(
            value=0,
            name="window_branches_total",
            description="All branches discovered in repo in our collection window",
            type="gauge",
        ),
        window_main_branch_commits=Metric(
            value=0,
            name="window_main_branch_commits",
            description="All branches discovered in repo in our collection window",
            type="gauge",
        ),
        window_pull_requests=Metric(
            value=0,
            name="window_pull_requests",
            description="All pull requests discovered in repo in our collection window",
            type="gauge",
        ),
        window_releases=Metric(
            value=0,
            name="window_releases",
            description="All releases discovered in repo in our collection window",
            type="gauge",
        ),
        windowed_mttr_secs=Metric(
            value=0,
            name="windowed_mttr_secs",
            description="Avg MTTR in our collection window",
            type="gauge",
        ),
        workflow_collection_time_secs=Metric(
            value=0,
            name="workflow_collection_time_secs",
            description="Time taken collecting Github Action Workflow data",
            type="gauge",
        ),
        # workflow_events
        # workflows
    )


def load_user(user: str) -> User:
    """
    Define loading of user object in one place
    (largely to keep the actual api file clean)
    """
    return User(
        user=user,
        avg_pr_time_open_secs=Metric(
            value=0,
            labels={"user": user},
            description="Time a PR stays open for a specific user",
            name="users_avg_user_pr_time_open_secs",
            type="gauge",
        ),
        branches_total=Metric(
            value=0,
            labels={"user": user},
            description="all branches a owned by a user",
            name="users_branches_total",
            type="counter",
        ),
        closed_pull_requests_total=Metric(
            value=0,
            labels={"user": user},
            description="All PRs closed by a user",
            name="users_closed_pull_requests_total",
            type="counter",
        ),
        commits_total=Metric(
            value=0,
            labels={"user": user},
            description="Commits by a user",
            name="users_commits_total",
            type="counter",
        ),
        draft_pull_requests_total=Metric(
            value=0,
            labels={"user": user},
            description="All draft PRs by a user",
            name="users_draft_pull_requests_total",
            type="counter",
        ),
        last_commit_time_secs=Metric(
            value=0,
            labels={"user": user},
            description="Timestamp of last commit for a user",
            name="users_last_commit_time_secs",
            type="gauge",
        ),
        merged_pull_requests_total=Metric(
            value=0,
            labels={"user": user},
            description="All PRs merged by a user",
            name="users_merged_pull_requests_total",
            type="counter",
        ),
        open_pull_requests_total=Metric(
            value=0,
            labels={"user": user},
            description="All PRs closed by a user",
            name="users_open_pull_requests_total",
            type="counter",
        ),
        pr_time_open_secs_total=Metric(
            value=0,
            labels={"user": user},
            description="Total time (in seconds) that PRs for a user are open",
            name="users_pr_time_open_secs_total",
            type="counter",
        ),
        pull_requests_total=Metric(
            value=0,
            labels={"user": user},
            description="All PRs closed by a user",
            name="users_pull_requests_total",
            type="counter",
        ),
        releases_total=Metric(
            value=0,
            labels={"user": user},
            description="All releases created by a user",
            name="users_releases_total",
            type="counter",
        ),
        window_branches=Metric(
            value=0,
            labels={"user": user},
            description="All branches owned by a user in our collection window",
            name="users_window_branches_total",
            type="gauge",
        ),
        window_commits=Metric(
            value=0,
            labels={"user": user},
            description="All commits by a user in our collection window",
            name="users_window_commits_total",
            type="gauge",
        ),
        window_pull_requests=Metric(
            value=0,
            labels={"user": user},
            description="All pull requests by a user in our collection window",
            name="users_window_pull_reqeusts_total",
            type="gauge",
        ),
        window_releases=Metric(
            value=0,
            labels={"user": user},
            description="All releases by a user in our collection window",
            name="users_window_releases_total",
            type="gauge",
        ),
        workflows=dict(),
    )


def load_config(config_file):
    """
    consistently load and format config file into config dictionary
    """
    config = yaml.safe_load(open(config_file, "r", encoding="utf-8").read())
    for k, _ in enumerate(config["repos"]):
        config["repos"][k]["folder"] = config["repo_folder"]
    return config
