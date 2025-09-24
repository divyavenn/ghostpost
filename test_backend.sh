#!/bin/bash
# usage: 
#  1. run `./setup_venv.sh`
#  2. run `./start_backend.sh`
#  3. run this to test the /comment endpoint


curl -X 'POST' \
  'http://localhost:8000/comment?prompt=bruh%20moment&model=divya-2-bon' \
  -H 'accept: application/json' \
  -d '' 2>&1 | tee bruh_moment_response.txt

