#!/bin/bash
# Wrapper script to check scraper statistics for an account

cd "$(dirname "$0")/backend" || exit 1

if [ -z "$1" ]; then
    echo "Usage: ./scraper-stats.sh <username> [--detailed]"
    echo ""
    echo "Examples:"
    echo "  ./scraper-stats.sh divya_venn"
    echo "  ./scraper-stats.sh divya_venn --detailed"
    echo "  ./scraper-stats.sh divya_venn -d"
    exit 1
fi

python scraper_stats.py "$@"
