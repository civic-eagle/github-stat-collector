"""
Defaults for some internal data
"""
from typing import TypedDict

DEFAULT_WINDOW = 1

class Workflow(TypedDict):
    retries: int
    last_run: None
    window_runs_total: int
    runs: dict

workflow_schema = {
    "retries": 0,
    "last_run": None,
    "window_runs_total": 1,
    "runs": dict(),
}

user_schema = {
    "avg_pr_time_open_secs": 0,
    "user": str(),
    "branches": list(),
    "branches_total": 0,
    "closed_pull_requests_total": 0,
    "commits_total": 0,
    "draft_pull_requests_total": 0,
    "events": dict(),
    "last_commit_time_secs": 0,
    "merged_pull_requests_total": 0,
    "open_pull_requests_total": 0,
    "pr_time_open_secs_total": 0,
    "pull_requests_total": 0,
    "releases_total": 0,
    "window_branches": 0,
    "window_commits": 0,
    "window_pull_requests": 0,
    "window_releases": 0,
    "workflows": dict(),
    "workflow_totals": dict(),
}

user_login_cache = {
    "names": dict(),
    "logins": dict(),
}

stats = {
    "branches_total": 0,
    "branches_collection_time_secs": 0,
    "empty_branches_total": 0,
    "protected_branches": 0,
    "window_branches": 0,
    "collection_date": None,
    "window": None,
    "commits_collection_time_secs": 0,
    "avg_commit_time_secs": 0,
    "branch_commits": dict(),
    "commits_total": 0,
    "commits_window_total": 0,
    "unreleased_commits_total": 0,
    # count matching tags as we pass through PRs/etc.
    "tag_matches": {},
    # track PRs with labels/patterns that match our definition of a bug
    "bug_matches": [],
    "mttr_secs": 0,
    "windowed_mttr_secs": 0,
    "main_branch_commits_total": 0,
    "window_main_branch_commits": 0,
    "avg_pr_time_open_secs": 0,
    "closed_pull_requests_total": 0,
    "release_collection_time_secs": 0,
    "draft_pull_requests_total": 0,
    "pr_labels": dict(),
    "merged_pull_requests_total": 0,
    "open_pull_requests_total": 0,
    "pull_requests_total": 0,
    "pr_time_open_secs_total": 0,
    "window_pull_requests": 0,
    "pr_collection_time_secs": 0,
    "releases_total": 0,
    "window_releases": 0,
    "code_frequency": dict(),
    "total_collection_time_secs": 0,
    "commit_activity": dict(),
    "contributors": dict(),
    "punchcard": {
        "commits_total": 0,
        "sorted_days": list(),
        "days": dict(),
    },
    # "code_scanning": {
    #     "open": dict(),
    #     "closed": dict(),
    #     "dismissed": dict(),
    # },
    "users": dict(),
    "workflow_events": dict(),
    "workflows": dict(),
    "workflow_collection_time_secs": 0,
}

tmp_statobj = {
    "description": "",
    "labels": {},
    "measurement_type": "count",
    "name": "",
    "value": 0,
}
