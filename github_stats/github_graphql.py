from datetime import datetime
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import logging
import os
import pprint
import time


class GithubGraphQL(object):
    def __init__(self, config):
        self.log = logging.getLogger("github-stats.graphql_collection")
        auth_token = os.environ.get("GITHUB_TOKEN", None)
        if not auth_token:
            auth_token = config["repo"].get("github_token", None)
        if not auth_token:
            raise Exception("Cannot find Github auth token in environment or config")
        self.org = config["repo"]["org"]
        self.repo = config["repo"]["name"]
        self.ignored_workflows = config["repo"].get("ignored_workflows", list())
        self.ignored_statuses = config["repo"].get("ignored_statuses", ["queued"])
        self.main_branch = config["repo"]["branches"].get("main", "main")
        self.release_branch = config["repo"]["branches"].get("release", "main")
        self.non_user_events = ["schedule"]
        self.pagination = config["repo"].get("pagination", 30)
        self.rt_limit = config["repo"].get("rate_limit_buffer", 10)

        transport = RequestsHTTPTransport(
            url="https://api.github.com/graphql",
            verify=True,
            retries=3,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        self._gql_client = Client(transport=transport, fetch_schema_from_transport=True)
        self._gql_header = """
            query (%s) {
              rateLimit {
                cost
                remaining
                resetAt
              }
              repository(owner: "%s", name: "%s") {
        """

    def _check_rt(self, rt):
        """
        Should always have a rateLimit object like so:
        {'rateLimit': {'cost': 1, 'remaining': 4992, 'resetAt': '2022-04-11T22:48:32Z'},
        if we're nearly out of credits, we should wait until it resets to avoid getting blocked
        """
        if (
            rt["remaining"] < self.rt_limit
            or rt["remaining"] - rt["cost"] < self.rt_limit
        ):
            dt = datetime.strptime(rt["resetAt"], "%Y-%m-%dT%H:%M:%SZ")
            wait = dt.timestamp() - time.time()
            self.log.warning(f"About to hit rate limit. Waiting for {wait} seconds.")
            time.sleep(wait)

    def _graphql_query(self, firstquery, params=None, pagination=True):
        """
        Add default parameters of pagination and page (unless asked not to)

        We'll need some way to paginate
              pageInfo {
                endCursor
                hasNextPage
              }

        :returns: generator of results
        """
        if not params:
            params = dict()

        """
        So if we start with "\n     refs(...) {\n..."

        we first split on \n, which may give empty strings in the return object, so filter those out `if not f`
        Then we split on the first occurance of `(`, which should give us our primary key to read `split("(")[0]`
        Then finally strip any spaces/etc. from the resultant string
        """
        topkey = [f for f in firstquery.split("\n") if f][0].split("(")[0].strip()

        if pagination:
            params["pagination"] = {"type": "Int", "value": self.pagination}

        # this is terrible, but we need to define any variables passed into the query
        header = self._gql_header % (
            ",".join([f"${k}:{v['type']}!" for k, v in params.items()]),
            self.org,
            self.repo,
        )
        querystr = "%s%s}}" % (header, firstquery)

        value_params = {k: v["value"] for k, v in params.items()}
        self.log.debug(f"{querystr=}")
        self.log.debug(f"{value_params=}")
        res = self._gql_client.execute(gql(querystr), variable_values=value_params)
        self._check_rt(res["rateLimit"])
        data = res["repository"][topkey]
        yield data
        nextquery = firstquery.replace(") {", ", after: $page) {", 1)
        while data["pageInfo"]["hasNextPage"]:
            params["page"] = {"type": "String", "value": data["pageInfo"]["endCursor"]}
            header = self._gql_header % (
                ",".join([f"${k}:{v['type']}!" for k, v in params.items()]),
                self.org,
                self.repo,
            )
            querystr = "%s%s}}" % (header, nextquery)
            value_params = {k: v["value"] for k, v in params.items()}
            self.log.debug(pprint.pformat(querystr))
            self.log.debug(pprint.pformat(value_params))
            res = self._gql_client.execute(gql(querystr), variable_values=value_params)
            self._check_rt(res["rateLimit"])
            data = res["repository"][topkey]
            yield data

    def test_query(self):
        for k in self._graphql_query(
            """
            refs(first: $pagination, refPrefix: "refs/heads/") {
              edges {
                node {
                  name
                }
              }
              pageInfo {
                endCursor
                hasNextPage
              }
            }
        """
        ):
            self.log.info(f"Processing object {pprint.pformat(k)}...")

    def test_query_2(self):
        for k in self._graphql_query(
            """
            releases(first: $pagination) {
              edges {
                node {
                  createdAt
                  name
                  author {
                    login
                  }
                }
              }
              pageInfo {
                endCursor
                hasNextPage
              }
            }
        """
        ):
            self.log.info(f"Processing object {pprint.pformat(k)}...")
