from github_stats.outputs import StatsOutput


class GrafanaCloud(StatsOutput):
    def __init__(self, config):
        super().__init__(config)
        grafana_config = config.get("grafana_cloud", {})
        if not grafana_config:
            raise Exception("Missing load grafana_cloud config section in config")
