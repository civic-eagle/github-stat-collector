#!/usr/bin/env python3

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import copy
from datetime import datetime, timedelta
import logging
import os
import time
import statistics

# local imports
from github_stats.github_api import GithubAccess
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
        default=30,
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
        end_date = args.timestamp
        end_time = datetime.utcfromtimestamp(end_date)
        base_date = (
            datetime.utcfromtimestamp(end_date) - timedelta(args.window)
        ).timestamp()
        # starttime = time.time()
        gh = GithubAccess(local_config)
        last_release = None
        all_releases_commit_deltas_in_minutes = []
        all_releases_total_delta_in_minutes = 0
        all_releases_total_commits = 0
        releases = list(gh.repo.releases)
        for release in releases:
            if release[1] < base_date or release[1] > end_date:
                logger.debug(
                    f"{release[0]}:{release[1]} outside release window {base_date}:{end_date}"
                )
                continue
            logger.info(
                f"{release[0]} on {release[1]} by {release[2]}",
            )

            if last_release:
                total_delta = 0
                deltas_in_minutes = []
                commits = gh.repo.commits_between_releases(last_release, release)
                for commit in commits:
                    delta_in_minutes = (commit.commit_time - release[1]) / 60
                    deltas_in_minutes.append(delta_in_minutes)
                    total_delta += delta_in_minutes
                release_average_delta_in_hours = round(total_delta / 60 / len(commits))
                release_median_delta_in_hours = round(
                    statistics.median(deltas_in_minutes) / 60
                )
                lead_time_msg = "lead time for commit in release, in hours"
                logger.info(
                    f"Average {lead_time_msg}: {release_average_delta_in_hours}",
                )
                logger.info(
                    f"Median {lead_time_msg}: {release_median_delta_in_hours}",
                )

                all_releases_total_commits += len(commits)
                all_releases_total_delta_in_minutes += total_delta
                all_releases_commit_deltas_in_minutes += deltas_in_minutes

            last_release = release

        window_message = f"{args.window} days before {end_time}"
        if len(releases) > 0 and all_releases_total_commits > 0:
            average_in_hours = round(
                all_releases_total_delta_in_minutes / 60 / all_releases_total_commits
            )
            median_in_hours = round(
                statistics.median(all_releases_commit_deltas_in_minutes) / 60
            )
            lead_time_msg = "lead time for commit->release, in hours"
            logger.info(
                f"Analyzed {len(releases)} releases found in {window_message}",
            )
            logger.info(f"Average {lead_time_msg}: {average_in_hours}")
            logger.info(f"Median {lead_time_msg}: {median_in_hours}")
        else:
            logger.info(
                f"Found no releases in specified window of {window_message}",
            )


if __name__ == "__main__":
    main()
