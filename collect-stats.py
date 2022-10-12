#!/usr/bin/env python3

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import copy
from datetime import datetime
import logging
import os
import time

# local imports
from github_stats.github_api import GithubAccess
from github_stats.outputs.influx import InfluxOutput
from github_stats.util import load_config

SCRIPTDIR = os.path.dirname(os.path.realpath(__file__))


def cli_opts():
    """
    Process CLI options
    """
    parser = ArgumentParser(
        description="Collect data about Github Actions",
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
        influx = InfluxOutput(local_config, timestamp)
        gh.load_all_stats(timestamp, args.window)
        influx.format_stats(gh.stats)
        influx.write_stats()

        logger.info(
            f"Loaded, formatted, and sent {influx.output_stat_count} stats in {time.time() - starttime} seconds"
        )


if __name__ == "__main__":
    main()
