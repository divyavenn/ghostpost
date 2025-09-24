#!/bin/bash 
# one time setup for .venv 
uv python install 3.11
uv venv -p 3.11 .venv
uv sync --group dev
uv run playwright install --with-deps

