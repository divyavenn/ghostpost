uv sync 
uv pip compile pyproject.toml > requirements.txt
modal deploy main.py