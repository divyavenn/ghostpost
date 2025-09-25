# reads pyproject.toml to determine dependencies
# resloves dependency graph 
# creates a virtual environment in the .venv/ directory
# writes uv.lock
# install all dependencies + developer tools 
uv sync --group dev
# uv run ensures the command is run inside the correct venv
# the Python package (playwright) only ships the client library + bindings
# separate installer fetches the right, up-to-date browser binaries + system libraries for your OS
uv run playwright install --with-deps

