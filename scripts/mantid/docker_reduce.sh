#!/usr/bin/env bash
# Run the simple-reduction tool inside the Docker container.
# Usage: ./docker_reduce.sh <event-file> <template> [options]
#
# Example:
#   ./docker_reduce.sh data/events/REF_L_12345.nxs.h5 data/templates/REF_L_sample.xml
#   ./docker_reduce.sh data/events/REF_L_12345.nxs.h5 data/templates/REF_L_sample.xml --output-dir results/reduced

set -euo pipefail

docker compose run --rm analyzer simple-reduction "$@"
