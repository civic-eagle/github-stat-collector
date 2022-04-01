"""
This output leverages the InfluxDB line protocol to write to a defined output
"""
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import logging
import os

# local imports
from github_stats.outputs import StatsOutput


class InfluxOutput(StatsOutput):
    def __init__(self, config, timestamp=0.0):
        super().__init__(config, timestamp)
        influx_config = config.get("influx", {})
        if not influx_config:
            raise Exception("Can't load influx config section")
        self.log = logging.getLogger("github-stats.output.influx")

        token = os.environ.get("INFLUX_TOKEN", None)
        if not token:
            token = influx_config.get("auth_token", None)
        if not token:
            raise Exception("Cannot find Influx auth token in environment or config")
        self.bucket = influx_config.get("bucket", "")
        self.org = influx_config.get("org", "")

        self.client = InfluxDBClient(
            url=influx_config["endpoint"],
            token=token,
            org=self.org,
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.output_stats = list()
        self.output_stat_count = 0

    def format_stats(self, stats_object):
        """
        Because influx stats require a 'measurement' and a list of 'fields'
        to define the metric names we will create, we need to break up
        the more prometheus-style metrics that our basic output formatting
        produces...
        Since all stat names have at least two 'field's if we break them up
        by '_' (thanks, prometheus standard!), this is relatively simple.
        1. "measurement" gets everything up to the last field
        2. "fields" gets the last 'field' of 'name'
        """
        self.output_stats = [
            {
                "measurement": "_".join(stat["name"].split("_")[:-1]),
                "tags": stat["labels"],
                # object passes around as a datetime.datetime
                "time": stat["timestamp"].timestamp(),
                "fields": {stat["name"].split("_")[-1]: stat["value"]},
            }
            for stat in super().format_stats(stats_object)
        ]
        self.output_stat_count = len(self.output_stats)

    def write_stats(self):
        self.log.info(
            f"Attempting to write {self.output_stat_count} metrics to Influx..."
        )
        for stat in self.output_stats:
            self.write_api.write(self.bucket, self.org, stat)
        self.write_api.close()
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
