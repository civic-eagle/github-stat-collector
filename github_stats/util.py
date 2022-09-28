import logging
import regex
import yaml

utillog = logging.getLogger("github-stats.util")


def load_patterns(tag_patterns=[], bug_patterns={}):
    """
    compile and format regex pattern matching
    """
    tag_matches = {tag["name"]: regex.compile(tag["pattern"]) for tag in tag_patterns}

    bug_matches = [regex.compile(p) for p in bug_patterns.get("patterns", [])]
    pr_matches = [label for label in bug_patterns.get("labels", [])]
    utillog.debug(f"{tag_matches=}, {bug_matches=}, {pr_matches=}")
    return tag_matches, bug_matches, pr_matches


def load_config(config_file):
    """
    consistently load and format config file into config dictionary
    """
    config = yaml.safe_load(open(config_file, "r", encoding="utf-8").read())
    for k in config["repos"].keys():
        config[k]["folder"] = config["repo_folder"]
    return config
