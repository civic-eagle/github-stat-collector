import logging
import regex

from github_stats.schema import User, Stats, Metric

utillog = logging.getLogger("github-stats.util")


def load_patterns(tag_patterns=[], bug_patterns={}):

    tag_matches = {tag["name"]: regex.compile(tag["pattern"]) for tag in tag_patterns}

    bug_matches = [regex.compile(p) for p in bug_patterns.get("patterns", [])]
    pr_matches = [label for label in bug_patterns.get("labels", [])]
    utillog.debug(f"{tag_matches=}, {bug_matches=}, {pr_matches=}")
    return tag_matches, bug_matches, pr_matches


def load_stats() -> Stats:
    return Stats(
        pull_requests_total=Metric(
            value=0,
            name="pull_requests_total",
            description="All pull requests discovered in repo",
            type="counter",
        ),
        open_pull_requests_total=Metric(
            value=0,
            name="open_pull_requests_total",
            description="All open pull requests discovered in repo",
            type="counter",
        ),
        draft_pull_requests_total=Metric(
            value=0,
            name="draft_pull_requests_total",
            description="All draft pull requests discovered in repo",
            type="counter",
        ),
        closed_pull_requests_total=Metric(
            value=0,
            name="closed_pull_requests_total",
            description="All closed pull requests discovered in repo",
            type="counter",
        ),
        merged_pull_requests_total=Metric(
            value=0,
            name="merged_pull_requests_total",
            description="All merged pull requests discovered in repo",
            type="counter",
        ),
        window_pull_requests=Metric(
            value=0,
            name="window_pull_requests",
            description="All pull requests discovered in repo in our collection window",
            type="gauge",
        ),
    )


def load_user(user: str) -> User:
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
