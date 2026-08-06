#!/bin/sh
set -eu
base_url="${1:-http://localhost}"
curl --fail --silent --show-error --output /dev/null "$base_url/"
