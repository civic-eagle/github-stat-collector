"""
Hold typed objects for the data we collect
(makes converting to different outputs easier)
"""
from datetime import datetime
from typing import TypedDict, Dict, Optional, Tuple, List

DEFAULT_WINDOW = 1


class Metric(TypedDict):
    description: str
    name: str
    type: str
    labels: Optional[Dict[str, str]]
    value: float


class Workflow(TypedDict):
    last_run: None
    retries: Metric
    runs: dict
    window_runs_total: Metric


class User(TypedDict):
    avg_pr_time_open_secs: Metric
    branches_total: Metric
    closed_pull_requests_total: Metric
    commits_total: Metric
    draft_pull_requests_total: Metric
    events: Optional[dict] = None
    last_commit_time_secs: Metric
    merged_pull_requests_total: Metric
    open_pull_requests_total: Metric
    pr_time_open_secs_total: Metric
    pull_requests_total: Metric
    releases_total: Metric
    user: str
    window_branches: Metric
    window_commits: Metric
    window_pull_requests: Metric
    window_releases: Metric
    workflows: Dict[str, Workflow]
    workflow_totals: Optional[dict] = None


class LabelledPRs(TypedDict):
    labelled_prs_total: Metric
    window_labelled_prs_total: Metric


class BranchCommits(TypedDict):
    commits_total: Metric
    commits_window_total: Metric


class CodeFrequency(TypedDict):
    additions: Metric
    deletions: Metric


class CommitActivity(TypedDict):
    daily: Dict[str, Metric]
    deletions: Metric


class UserLoginCache(TypedDict):
    logins: Dict[str, str]
    names: Dict[str, str]


class Contributor(TypedDict):
    commits_total: Metric
    weeks: Dict[str, WeeklyUserCommits]


class WeeklyUserCommits(TypedDict):
    commits: Metric
    additions: Metric
    deletions: Metric


class Stats(TypedDict, total=False):
    avg_commit_time_secs: Metric
    avg_pr_time_open_secs: Metric
    branches_collection_time_secs: Metric
    branch_commits: Dict[str, BranchCommits]
    branches_total: Metric
    """
    track PRs with labels/patterns that match our definition of a bug
    (title, commit sha, timestamp)
    """
    bug_matches: List[Tuple(str, str, int)]
    closed_pull_requests_total: Metric
    code_frequency: Dict[str, CodeFrequency]
    collection_date: datetime
    commit_activity: Dict[str, CommitActivity]
    commits_collection_time_secs: Metric
    commits_total: Metric
    commits_window_total: Metric
    contributor_collection_time_secs: Metric
    contributors: Dict[str, Contributor]
    draft_pull_requests_total: Metric
    empty_branches_total: Metric
    main_branch_commits_total: Metric
    merged_pull_requests_total: Metric
    mttr_secs: Metric
    open_pull_requests_total: Metric
    pull_requests_total: Metric
    pr_collection_time_secs: Metric
    pr_labels: Dict[str, LabelledPRs]
    pr_time_open_secs_total: Metric
    protected_branches_total: Metric
    # "punchcard": {
    #    "commits_total": 0,
    #    "sorted_days": list(),
    #    "days": dict(),
    # },
    release_collection_time_secs: Metric
    releases_total: Metric
    # count matching tags as we pass through PRs/etc.
    tag_matches: Dict[str, Metric]
    total_collection_time_secs: Metric
    unreleased_commits_total: Metric
    users: Optional[Dict[str, User]]
    window: int
    window_branches_total: Metric
    window_main_branch_commits: Metric
    window_pull_requests: Metric
    window_releases: Metric
    windowed_mttr_secs: Metric
    workflow_collection_time_secs: Metric
    workflow_events: dict
    workflows: Dict[str, Workflow]
    # "code_scanning": {
    #     "open": dict(),
    #     "closed": dict(),
    #     "dismissed": dict(),
    # },


tmp_statobj = {
    "description": "",
    "labels": {},
    "measurement_type": "count",
    "name": "",
    "value": 0,
}
