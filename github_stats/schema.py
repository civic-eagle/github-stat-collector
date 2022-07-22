"""
Defaults for some internal data
"""
from datetime import datetime
from typing import TypedDict, Dict, Optional

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


class UserLoginCache(TypedDict):
    logins: Dict[str, str]
    names: Dict[str, str]


class Stats(TypedDict):
    avg_commit_time_secs: Metric
    branches_total: Metric
    branches_collection_time_secs: Metric
    # track PRs with labels/patterns that match our definition of a bug
    bug_matches: list
    code_frequency: dict
    collection_date: datetime
    commit_activity: dict
    commits_collection_time_secs: Metric
    contributor_collection_time_secs: Metric
    contributors: dict
    empty_branches_total: Metric
    branch_commits: dict
    commits_total: Metric
    commits_window_total: Metric
    mttr_secs: Metric
    main_branch_commits_total: Metric
    window_main_branch_commits: Metric
    avg_pr_time_open_secs: Metric
    closed_pull_requests_total: Metric
    draft_pull_requests_total: Metric
    merged_pull_requests_total: Metric
    open_pull_requests_total: Metric
    pull_requests_total: Metric
    pr_collection_time_secs: Metric
    pr_labels: Dict[str, Metric]
    pr_time_open_secs_total: Metric
    protected_branches_total: Metric
    release_collection_time_secs: Metric
    releases_total: Metric
    # count matching tags as we pass through PRs/etc.
    tag_matches: dict
    total_collection_time_secs: Metric
    unreleased_commits_total: Metric
    users: Dict[str, User]
    window: int
    window_branches_total: Metric
    window_pull_requests: Metric
    window_releases: Metric
    windowed_mttr_secs: Metric
    workflow_collection_time_secs: Metric
    workflow_events: dict
    workflows: Dict[Workflow]
    # "punchcard": {
    #    "commits_total": 0,
    #    "sorted_days": list(),
    #    "days": dict(),
    # },
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
