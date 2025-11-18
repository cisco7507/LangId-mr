#!/bin/bash

API_URL="http://localhost:8080/jobs"
DIR="/Users/gsp/Downloads/test"

for f in "$DIR"/*; do
    if [ -f "$f" ]; then
        echo "Submitting: $f"
        curl -s -X POST "$API_URL" \
            -F "file=@$f" \
            -H "Expect:"  # prevent curl 417 issues
        echo ""
    fi
done
