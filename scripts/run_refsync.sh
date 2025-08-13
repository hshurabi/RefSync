#!/usr/bin/env bash
set -euo pipefail
refsync "${1:-examples/sample_library}" --verbose
