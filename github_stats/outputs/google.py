"""
Google Cloud leverages the OpenCensus library (very similar to the OpenTelemetry library) to write data

More documentation about OpenCensus is here: https://opencensus.io
More documentation on the StackDriver extension is here: https://cloud.google.com/monitoring/custom-metrics/open-census
"""
from github_stats.outputs import StatsOutput
from opencensus.ext.stackdriver import stats_exporter
from opencensus.stats import aggregation, measure, stats, view
from opencensus.tags import tag_key, tag_map, tag_value
import logging
import time


class GoogleOutput(StatsOutput):
    def __init__(self, config):
        super().__init__(config)
        google_config = config.get("google", {})
        if not google_config:
            raise Exception("Can't load Google config section")
        self.log = logging.getLogger("github-stats.output.google")
        """
        OpenCensus emits data on an interval (rather immediately)

        We need to define an interval on which the export will happen
        so we know how long to wait after creating our metrics
        to ensure all metrics are exported. Basically, we're making
        an async loop synchronous through time.sleep() functions.
        It's a hack, but it's a recommended hack from OpenCensus' docs.

        We'll default to a relatively aggressive interval to make the
        write loop reasonably fast.
        """
        self.export_rate = google_config.get("export_interval", 10)
        self.view_manager = stats.ViewManager()
        self.exporter = stats_exporter.new_stats_exporter(
            stats_exporter.Options(
                project_id=google_config["project_id"],
                # strip the 'opencensus_task' label
                default_monitoring_labels={},
                resource="global",
            ),
            interval=self.export_rate,
        )
        self.view_manager.register_exporter(self.exporter)
        self.output_stats = dict()
        self.output_stat_count = 0

    def format_stats(self, stats_object):
        """
        We reformat the collected stats so we can cluster all
        measurements for a single view (metric) together

        :returns: None
        """
        formatted_stats = super().format_stats(stats_object)

        for stat in formatted_stats:
            self.output_stat_count += 1
            if stat["name"] in self.output_stats:
                self.output_stats[stat["name"]]["stats"].append(stat)
            else:
                # This is a new view/metric. Recreate the schema
                self.output_stats[stat["name"]] = {
                    "stats": [stat],
                    "keys": [k for k in stat["labels"].keys()],
                    "description": stat["description"],
                    "measurement_type": stat["measurement_type"],
                }
        """
        StackDriver doesn't support negative values, so we have to do some hacking
        to actually track line changes

        'weekly_contributor_line_changes_total': {'description': 'Weekly line changes made by a contributor',
                                           'keys': ['repository_name', 'name', 'week', 'type'],
                                           'measurement_type': 'count',
                                           'stats': [{'description': 'Weekly line changes made by a contributor',
                                                      'labels': {'name': 'Jefferson Jeffries',
                                                                 'repository_name': 'repo',
                                                                 'type': 'additions',
                                                                 'week': '2022-03-20 '00:00:00'},
                                                      'measurement_type': 'count',
                                                      'name': 'weekly_contributor_line_changes_total',
                                                      'value': 107},
                                                     {'description': 'Weekly line changes made by a contributor',
                                                      'labels': {'name': 'Jefferson Jeffries',
                                                                 'repository_name': 'repo',
                                                                 'type': 'deletions',
                                                                 'week': '2022-03-20 00:00:00'},
                                                      'measurement_type': 'count',
                                                      'name': 'weekly_contributor_line_changes_total',
                                                      'value': 99}},
        'weekly_line_changes_total': {'description': 'count of line changes during a week',
                               'keys': ['repository_name', 'type', 'week'],
                               'measurement_type': 'count',
                               'stats': [{'description': 'count of line changes during a week',
                                          'labels': {'repository_name': 'repo',
                                                     'type': 'additions',
                                                     'week': '2022-03-20 00:00:00'},
                                          'measurement_type': 'count',
                                          'name': 'weekly_line_changes_total',
                                          'value': 389},
                                         {'description': 'count of line changes during a week',
                                          'labels': {'repository_name': 'repo',
                                                     'type': 'deletions',
                                                     'week': '2022-03-20 00:00:00'},
                                          'measurement_type': 'count',
                                          'name': 'weekly_line_changes_total',
                                          'value': -294}]},
        """
        filtered_keys = ["type"]

        contrib_changes = self.output_stats.pop(
            "weekly_contributor_line_changes_total", {}
        )
        if contrib_changes:
            self.output_stats["weekly_contributor_line_changes_total"] = {
                "description": contrib_changes["description"],
                "keys": [t for t in contrib_changes["keys"] if t not in filtered_keys],
                "measurement_type": contrib_changes["measurement_type"],
                "stats": [],
            }
            users = dict()
            for stat in contrib_changes["stats"]:
                name = stat["labels"]["name"]
                if name not in users:
                    users[name] = {
                        "description": stat["description"],
                        "labels": {
                            k: v
                            for k, v in stat["labels"].items()
                            if k not in filtered_keys
                        },
                        "measurement_type": stat["measurement_type"],
                        "name": stat["name"],
                        "value": stat["value"],
                    }
                else:
                    users[name]["value"] += stat["value"]
            self.output_stats["weekly_contributor_line_changes_total"]["stats"] = [
                v for v in users.values()
            ]

        total_changes = self.output_stats.pop("weekly_line_changes_total", {})
        if total_changes:
            self.output_stats["weekly_line_changes_total"] = {
                "description": total_changes["description"],
                "keys": [t for t in total_changes["keys"] if t not in filtered_keys],
                "measurement_type": total_changes["measurement_type"],
                "stats": [],
            }
            tc = {
                "description": total_changes["description"],
                "labels": {},
                "measurement_type": total_changes["measurement_type"],
                "name": "",
                "value": 0,
            }
            for stat in total_changes["stats"]:
                tc["value"] += stat["value"]
                tc["labels"] = {
                    k: v for k, v in stat["labels"].items() if k not in filtered_keys
                }
                tc["name"] = stat["name"]
            self.output_stats["weekly_line_changes_total"]["stats"] = [tc]

    def write_stats(self):
        """
        Actually write stats to stackdriver

        The steps are a bit confusing, but basically:
        1. Create a list of the tag keys
        2. Create a map of tag key objects to tag value objects
        3. Create the actual measurement object to write
        4. Create the "view" of the measurement (this contains any aggregation required/etc.)
        5. actually write the value to the measurement
        6. attach the tag map to the measurement and record the full series created

        :returns: None
        """
        self.log.info(f"Will attempt to write {self.output_stat_count} stats")
        starttime = time.time()

        for viewname, data in self.output_stats.items():
            """
            First we generate the measure and view for this
            group of stats.
            """
            if data["measurement_type"] in self.float_measurements:
                measureobj = measure.MeasureFloat(
                    viewname,
                    data["description"],
                    data["measurement_type"],
                )
            else:
                measureobj = measure.MeasureInt(
                    viewname,
                    data["description"],
                    data["measurement_type"],
                )
            m_view = view.View(
                viewname,
                data["description"],
                data["keys"],
                measureobj,
                aggregation.LastValueAggregation(),
            )
            self.view_manager.register_view(m_view)
            """
            Now we add each measurement for the created view
            in one go. This should help ensure we get all
            potential stats written correctly
            """
            for stat in data["stats"]:
                self.log.debug(f"Attempting to write {stat} to Google")

                tagmap = tag_map.TagMap()
                for tk, tv in stat["labels"].items():
                    tagmap.insert(tag_key.TagKey(tk), tag_value.TagValue(tv))

                mmap = stats.stats.stats_recorder.new_measurement_map()
                if stat["measurement_type"] in self.float_measurements:
                    mmap.measure_float_put(measureobj, stat["value"])
                else:
                    mmap.measure_int_put(measureobj, stat["value"])
                mmap.record(tagmap)

        # ensure at least one flush happens at the end
        time.sleep(self.export_rate + 10)
        self.log.info(f"Wrote stats in {time.time() - starttime} seconds")
