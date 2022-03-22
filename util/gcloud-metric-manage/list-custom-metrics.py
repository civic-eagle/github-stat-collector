#!/usr/bin/env python3

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from google.cloud import monitoring_v3

PREFIX = "custom.googleapis.com/"


def cli_opts():
    """
    Process CLI options
    """
    parser = ArgumentParser(
        description="List all custom metrics for a project",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--project",
        required=True,
        help="GCP Project name",
    )
    return parser.parse_args()


def main():
    args = cli_opts()
    client = monitoring_v3.MetricServiceClient()
    project = f"projects/{args.project}"
    for metric in client.list_metric_descriptors(name=project):
        if not metric.type.startswith(PREFIX):
            continue
        print(metric.type.removeprefix(PREFIX))


if __name__ == "__main__":
    main()
