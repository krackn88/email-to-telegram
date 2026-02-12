#!/usr/bin/env bash
# Run forward with unbuffered output so you always see prints
cd "$(dirname "$0")"
exec .venv/bin/python -u main.py forward
