import logging
import regex

utillog = logging.getLogger("github-stats.util")


def load_patterns(tag_patterns=[], bug_patterns={}):

    tag_matches = {tag["name"]: regex.compile(tag["pattern"]) for tag in tag_patterns}

    bug_matches = [regex.compile(p) for p in bug_patterns.get("patterns", [])]
    pr_matches = [label for label in bug_patterns.get("labels", [])]
    utillog.debug(f"{tag_matches=}, {bug_matches=}, {pr_matches=}")
    return tag_matches, bug_matches, pr_matches
