#!/usr/bin/env python3

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from datetime import datetime
import logging
import os
import time
import yaml
from github_stats.github_api import GithubAccess
from github_stats.outputs.google import GoogleOutput

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
        "--end-date",
        default=datetime.today().strftime("%Y-%m-%d"),
        type=str,
        help="Date to start looking at data from",
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
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    starttime = time.time()
    goog = GoogleOutput(config)
    gh = GithubAccess(config)
    gh.load_all_stats(end_date, args.window)
    goog.format_stats(gh.stats)
    goog.write_stats()

    logger.info(
        f"Loaded, formatted, and sent {goog.output_stat_count} stats in {time.time() - starttime} seconds"
    )


if __name__ == "__main__":
    main()
