"""
This output leverages the InfluxDB line protocol to write to a defined output
"""
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.write_precision import WritePrecision
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

        meta = {"url": influx_config["endpoint"]}
        token = os.environ.get("INFLUX_TOKEN", "")
        if not token:
            token = influx_config.get("auth_token", "")
        meta["token"] = token
        self.bucket = influx_config.get("bucket", "")
        self.org = influx_config.get("org", "")
        if self.bucket:
            meta["bucket"] = self.bucket
        if self.org:
            meta["org"] = self.org
        self.prefix = influx_config.get("metric_prefix", "")
        self.client = InfluxDBClient(**meta)
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
        1. "measurement" gets everything up to the last field of 'name'
        2. "fields" gets the last 'field' of 'name'
        """
        self.output_stats = [
            {
                "measurement": "_".join([self.prefix] + stat["name"].split("_")[:-1]),
                "tags": stat["labels"],
                "time": int(stat["timestamp"].timestamp()),
                "fields": {stat["name"].split("_")[-1]: stat["value"]},
            }
            for stat in super().format_stats(stats_object)
        ]
        self.output_stat_count = len(self.output_stats)
        for stat in self.output_stats:
            self.log.debug(f"Gonna write {stat} to influx")

    def write_stats(self):
        self.log.info(
            f"Attempting to write {self.output_stat_count} metrics to Influx..."
        )
        self.write_api.write(
            self.bucket, self.org,
            self.output_stats,
            write_precision=WritePrecision.S,
        )
        self.write_api.close()
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
