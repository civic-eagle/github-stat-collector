#!/usr/bin/env python3

"""
Per https://cloud.google.com/monitoring/docs/samples/monitoring-delete-metric
"""
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from google.cloud import monitoring_v3


def cli_opts():
    """
    Process CLI options
    """
    parser = ArgumentParser(
        description="delete custom metric from Google Cloud (StackDriver)",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "metrics",
        nargs="*",
        help="Name(s) of metrics to delete",
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
    prefix = f"projects/{args.project}/metricDescriptors/custom.googleapis.com"
    for metric in args.metrics:
        fullname = f"{prefix}/{metric}"
        print(f"Deleting {fullname}")
        client.delete_metric_descriptor(name=fullname)


if __name__ == "__main__":
    main()
