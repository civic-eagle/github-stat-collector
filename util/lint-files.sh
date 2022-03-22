#!/usr/bin/env bash

set -eo pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

FIX=${FIX:-no}

if [[ "${FIX}" == "yes" ]]; then
    _BLACK_SWITCHES="--diff"
else
    _BLACK_SWITCHES="--check --diff"
fi

printf "Linting python...\n"
# shellcheck disable=SC2086
docker run --rm -v "${SCRIPT_DIR}/../:/data" cytopia/black:latest ${_BLACK_SWITCHES} .
docker run --rm -v "${SCRIPT_DIR}/../:/apps" alpine/flake8:latest .

printf "\nLinting YAML files...\n"
docker run --rm -v "${SCRIPT_DIR}/../:/data" cytopia/yamllint -c yamllint.yml -s .

printf "\nLinting/validating shell scripts...\n"
while IFS= read -r -d '' filename; do
    realname=${filename##"$SCRIPT_DIR/../"}
    echo "processing ${realname}"
    docker run --rm -v "${SCRIPT_DIR}/../:/mnt" koalaman/shellcheck:latest -x "${realname}"
done < <(find "${SCRIPT_DIR}/../" -type f -name "*.sh" ! -path "*/.git/*" -print0)

# printf "\nValidating json files...\n"
# while IFS= read -r -d '' filename; do
#     realname=${filename##"$SCRIPT_DIR/../"}
#     echo "processing ${realname}"
#     python3 -c "import json;json.loads(open('$realname', 'r').read())" || exit 2
# done < <(find "${SCRIPT_DIR}/../" -type f -name "*.json" ! -path "*/packages/*" ! -path "*/node_modules/*" ! -path "*/.terraform/*" -print0)
