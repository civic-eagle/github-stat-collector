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
logger = logging.getLogger("github-stats")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def cli_opts():
    """
    Process CLI options
    """
    parser = ArgumentParser(
        description="Backfill data about Github Actions",
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
        "--start-timestamp",
        default=time.time() - 604800,
        type=float,
        help="UTC timestamp to start looking at data from",
    )
    parser.add_argument(
        "--stop-timestamp",
        default=time.time(),
        type=float,
        help="UTC timestamp to stop looking at data from",
    )
    parser.add_argument(
        "--timestamp-step",
        default=3600,
        type=float,
        help="Spacing (in seconds) between each collection (e.g. 14400 === 4 hours)",
    )
    parser.add_argument(
        "--sleep-time",
        default=3600,
        type=float,
        help="Time (in seconds) to wait between runs (will be <= 3600 seconds)",
    )
    return parser.parse_args()


def _hour_diff():
    """
    nearest floored hour to use to create our buckets
    (definitely want floor so subtraction always works)
    // is a flooring division function.
    Multiply again by the initial number to get the closest hour
    """
    current_time = time.time()
    hour_floor = int((current_time // 3600) * 3600)
    diff = current_time - hour_floor
    logger.debug("{diff=}")
    return diff


def _wait(positions):
    """
    This isn't perfect. There will still be some small amount (milliseconds) of drift
    each run because we have to do the math.
    But it's better than a basic sleep() function
    """
    diff = _hour_diff()
    for pos in positions:
        # if we find a position in our list, sleep for the remaining amount of time
        if diff <= pos:
            sleep_time = int(pos - diff)
            break
    else:
        """
        diff > pos[-1]
        This means we're near the top of the hour but past our last position
        So we need to subtract the diff from a total hour (to get time left in the hour)
        and add position 0's offset
        """
        sleep_time = int(3600 - diff) + positions[0]
    logger.debug(f"Sleeping for {sleep_time} seconds")
    time.sleep(sleep_time)


def main():
    args = cli_opts()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    """
    Bucket time into chunks based on our sleep time
    so we run the script at the same time(s) every hour
    """
    if args.sleep_time > 3600:
        sleep_time = 3600
    else:
        sleep_time = args.sleep_time
    positions = list()
    runs_per_hour = int(3600 / sleep_time)
    # drop the current time here because we don't need it
    diff = _hour_diff()
    # set our positions around the clock for when the job will run
    # using our diff as a 0-based offset
    for r in range(runs_per_hour):
        pos = int(sleep_time * r) + diff
        if pos > 3600:
            pos = pos - 3600
        positions.append(int(pos))
    positions = sorted(positions)
    logger.debug(f"{positions=}")

    # actually set up environment
    config = load_config(args.config)

    for run in range(
        int(args.start_timestamp),
        int(args.stop_timestamp),
        int(args.timestamp_step),
    ):
        for repo in config["repos"]:
            local_config = copy.deepcopy(config)
            local_config.pop("repos", None)
            local_config["repo"] = repo
            timestamp = datetime.utcfromtimestamp(run)
            logger.info(f"Processing data for {timestamp}...")
            # we should load GithubAccess every run to ensure we don't lose access tokens/etc.
            gh = GithubAccess(local_config)
            influx = InfluxOutput(local_config, timestamp)
            # retry stat collection a few times in case we get a failure
            for _ in range(3):
                try:
                    gh.load_all_stats(timestamp, args.window)
                    break
                except Exception:
                    pass
            influx.format_stats(gh.stats)
            influx.write_stats()
        # sleep for however long it takes to get to our next position
        _wait(positions)


if __name__ == "__main__":
    main()
