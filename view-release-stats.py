#!/usr/bin/env python3

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import copy
import logging
import os
import time

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
        gh = GithubAccess(local_config)
        gh.load_release_window_stats(end_date, args.window)


if __name__ == "__main__":
    main()
