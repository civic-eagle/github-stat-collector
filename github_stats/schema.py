"""
Defaults for some internal data
"""
DEFAULT_WINDOW = 1

user_schema = {
    "avg_pr_time_open_secs": 0,
    "total_branches": 0,
    "total_closed_pull_requests": 0,
    "total_commits": 0,
    "total_merged_pull_requests": 0,
    "total_open_pull_requests": 0,
    "total_pr_time_open_secs": 0,
    "total_pull_requests": 0,
    "total_releases": 0,
    "total_window_branches": 0,
    "total_window_pull_requests": 0,
    "total_window_releases": 0,
    "total_window_commits": 0,
    "events": dict(),
    "workflows": dict(),
    "workflow_totals": dict(),
    "branches": list(),
}

user_login_cache = {
    "names": dict(),
    "logins": dict(),
}

stats = {
    "branches": {
        "total_branches": 0,
        "total_window_branches": 0,
        "protected_branches": 0,
        "total_empty_branches": 0,
        "collection_time": 0,
    },
    "collection_date": None,
    "collection_time_secs": 0,
    "commits": {
        "branch_commits": dict(),
        "total_commits": 0,
        "window_commits": 0,
        "collection_time": 0,
    },
    "general": {
        "main_branch_commits": 0,
        "window_main_branch_commits": 0,
        "tag_matches": {},
    },
    "pull_requests": {
        "total_pull_requests": 0,
        "total_merged_pull_requests": 0,
        "total_pr_time_open_secs": 0,
        "avg_pr_time_open_secs": 0,
        "total_open_pull_requests": 0,
        "total_closed_pull_requests": 0,
        "total_window_pull_requests": 0,
        "total_draft_pull_requests": 0,
        "labels": dict(),
        "collection_time": 0,
    },
    "releases": {
        "total_releases": 0,
        "total_window_releases": 0,
        "releases": dict(),
        "collection_time": 0,
    },
    "repo_stats": {
        "code_frequency": dict(),
        "commit_activity": dict(),
        "contributors": dict(),
        "punchcard": {
            "total_commits": 0,
            "sorted_days": list(),
            "days": dict(),
        },
        "collection_time": 0,
    },
    # "code_scanning": {
    #     "open": dict(),
    #     "closed": dict(),
    #     "dismissed": dict(),
    # },
    "users": dict(),
    "workflows": {"events": dict(), "workflows": dict(), "collection_time": 0},
}

tmp_statobj = {
    "name": "",
    "labels": {},
    "value": 0,
    "description": "",
    "measurement_type": "count",
}
