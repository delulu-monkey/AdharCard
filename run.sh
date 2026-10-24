#!/usr/bin/env bash
set -a; [ -f .env ] && source .env; set +a
export LD_LIBRARY_PATH="$(echo "$PWD"/.venv/lib/python3.12/site-packages/nvidia/*/lib | tr ' ' ':'):$LD_LIBRARY_PATH"
exec uv run "$@"
