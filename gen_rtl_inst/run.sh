#!/usr/bin/env bash
set -euo pipefail

python3 -B ./src/gen_rtl_inst.py "$1"
