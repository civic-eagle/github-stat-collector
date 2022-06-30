"""
Defaults for some internal data
"""
DEFAULT_WINDOW = 1

user_schema = {
    "avg_pr_time_open_secs": 0,
    "branches_total": 0,
    "closed_pull_requests_total": 0,
    "commits_total": 0,
    "merged_pull_requests_total": 0,
    "open_pull_requests_total": 0,
    "draft_pull_requests_total": 0,
    "pr_time_open_secs_total": 0,
    "pull_requests_total": 0,
    "releases_total": 0,
    "window_branches": 0,
    "window_pull_requests": 0,
    "window_releases": 0,
    "window_commits": 0,
    "events": dict(),
    "workflows": dict(),
    "workflow_totals": dict(),
    "branches": list(),
    "last_commit_time_secs": 0,
}

user_login_cache = {
    "names": dict(),
    "logins": dict(),
}

stats = {
    "branches": {
        "branches_total": 0,
        "window_branches": 0,
        "protected_branches": 0,
        "empty_branches_total": 0,
        "collection_time_secs": 0,
    },
    "collection_date": None,
    "window": None,
    "collection_time_secs": 0,
    "commits": {
        "branch_commits": dict(),
        "commits_total": 0,
        "window_commits": 0,
        "avg_commit_time_secs": 0,
        "unreleasd_commits_total": 0,
    },
    # count matching tags as we pass through PRs/etc.
    "tag_matches": {},
    # track PRs with labels/patterns that match our definition of a bug
    "bug_matches": [],
    "mttr_secs": 0,
    "windowed_mttr_secs": 0,
    "main_branch_commits_total": 0,
    "window_main_branch_commits": 0,
    "pull_requests": {
        "pull_requests_total": 0,
        "merged_pull_requests_total": 0,
        "pr_time_open_secs_total": 0,
        "avg_pr_time_open_secs": 0,
        "open_pull_requests_total": 0,
        "closed_pull_requests_total": 0,
        "window_pull_requests": 0,
        "draft_pull_requests": 0,
        "labels": dict(),
        "collection_time_secs": 0,
    },
    "releases": {
        "releases_total": 0,
        "window_releases": 0,
        "releases": dict(),
        "collection_time_secs": 0,
    },
    "repo_stats": {
        "code_frequency": dict(),
        "commit_activity": dict(),
        "contributors": dict(),
        "punchcard": {
            "commits_total": 0,
            "sorted_days": list(),
            "days": dict(),
        },
        "collection_time_secs": 0,
    },
    # "code_scanning": {
    #     "open": dict(),
    #     "closed": dict(),
    #     "dismissed": dict(),
    # },
    "users": dict(),
    "workflows": {"events": dict(), "workflows": dict(), "collection_time_secs": 0},
}

tmp_statobj = {
    "name": "",
    "labels": {},
    "value": 0,
    "description": "",
    "measurement_type": "count",
}
