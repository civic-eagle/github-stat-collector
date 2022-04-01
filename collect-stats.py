#!/usr/bin/env python3

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from datetime import datetime
import logging
import os
import pprint
import time
import yaml

# local imports
from github_stats.github_api import GithubAccess
from github_stats.outputs.influx import InfluxOutput

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
    config = yaml.safe_load(open(args.config, "r", encoding="utf-8").read())
    timestamp = datetime.fromtimestamp(args.timestamp)
    starttime = time.time()
    gh = GithubAccess(config)
    influx = InfluxOutput(config, timestamp)
    gh.load_all_stats(timestamp, args.window)
    influx.format_stats(gh.stats)
    logger.info(f"{pprint.pformat(influx.output_stats)}")
    influx.format_stats(gh.stats)
    influx.write_stats()

    logger.info(
        f"Loaded, formatted, and sent {influx.output_stat_count} stats in {time.time() - starttime} seconds"
    )


if __name__ == "__main__":
    main()
