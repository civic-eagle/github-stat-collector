#!/usr/bin/env python3

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import copy
from datetime import datetime
import logging
import os
import time
import subprocess
import statistics

# local imports
from github_stats.github_api import GithubAccess
from github_stats.outputs.influx import InfluxOutput
from github_stats.util import load_config

SCRIPTDIR = os.path.dirname(os.path.realpath(__file__))

"""
Utility script to view release statistics (eg lead time).
Maybe the basis for different stats collection in the future. 
Run like: poetry run python view-release-stats.py -c config.yml -w 30
to see stats for rleeases in the last 30 days
"""


def cli_opts():
    """
    Process CLI options
    """
    parser = ArgumentParser(
        description="Collect data about Github Releases",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--debug", action="store_true", default=False, help="Show debug information"
    )
    parser.add_argument(
        "-c",
        "--config",
        default=f"{SCRIPTDIR}/config.yml",
        help="Config file location",
    )
    parser.add_argument(
        "-w",
        "--window",
        default=1,
        type=int,
        help="Number of days worth of data to collect",
    )
    parser.add_argument(
        "--timestamp",
        default=time.time(),
        type=float,
        help="UTC timestamp to start looking at data from",
    )
    return parser.parse_args()


def get_time_delta_in_minutes_from_iso_strings(timeStringA, timeStringB):
    timeA = datetime.fromisoformat(timeStringA)
    timeB = datetime.fromisoformat(timeStringB)
    delta = timeA - timeB
    return delta.total_seconds() / 60


def main():
    args = cli_opts()
    logger = logging.getLogger("github-stats")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    if args.debug:
        logger.setLevel(logging.DEBUG)
    config = load_config(args.config)
    for repo in config["repos"]:
        local_config = copy.deepcopy(config)
        local_config.pop("repos", None)
        local_config["repo"] = repo
        timestamp = datetime.utcfromtimestamp(args.timestamp)
        starttime = time.time()
        gh = GithubAccess(local_config)
        last_release = None
        releases = []
        for release in gh.return_releases(timestamp, args.window):
            releases.append(release)
        releases.reverse()  # Reverse so we have chronological

        all_releases_commit_deltas_in_minutes = []
        all_releases_total_delta_in_minutes = 0
        all_releases_total_commits = 0
        for release in releases:
            release_date_in_utc = release['published_at'].rstrip('Z') + '+00:00'  # datetime.fromisoformat hates the Z
            logger.log(logging.INFO, f"{release['tag_name']} on {release_date_in_utc} by {release['author']['login']}")

            if (last_release):
                commit_times_output = subprocess.check_output(
                    ["git", "log", "--format=%cI", f"{release['tag_name']}...{last_release['tag_name']}"],
                    cwd=f"{SCRIPTDIR}/repos/{repo['name']}"
                ).decode()
                commit_times_split = commit_times_output.split('\n')
                commit_times = [i for i in commit_times_split if i]  # eliminate empty strings
                total_delta = 0
                deltas_in_minutes = []
                for commit_time in commit_times:
                    delta_in_minutes = get_time_delta_in_minutes_from_iso_strings(release_date_in_utc, commit_time)
                    deltas_in_minutes.append(delta_in_minutes)
                    total_delta += delta_in_minutes
                release_average_delta_in_hours = round(total_delta / 60 / len(commit_times))
                release_median_delta_in_hours = round(statistics.median(deltas_in_minutes) / 60)
                logger.log(logging.INFO, f"Average delta for release, in hours: {release_average_delta_in_hours}")
                logger.log(logging.INFO, f"Median delta for release, in hours: {release_median_delta_in_hours}")

                all_releases_total_commits += len(commit_times)
                all_releases_total_delta_in_minutes += total_delta
                all_releases_commit_deltas_in_minutes += deltas_in_minutes

            last_release = release

        if len(releases) > 0:
            average_in_hours = round(all_releases_total_delta_in_minutes / 60 / all_releases_total_commits)
            median_in_hours = round(statistics.median(all_releases_commit_deltas_in_minutes) / 60)
            window_message = f"{args.window} days before {timestamp}"
            logger.log(logging.INFO, f"Analyzed {len(releases)} releases found in {window_message}")
            logger.log(logging.INFO, f"Average lead time in hours: {average_in_hours}")
            logger.log(logging.INFO, f"Median lead time in hours: {median_in_hours}")
        else:
            logger.log(logging.INFO, f"Found no releases in specified window of {window_message}")


if __name__ == "__main__":
    main()