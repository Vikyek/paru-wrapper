#!/bin/bash
set -e

cat << 'INPUT' | awk '/^(Depends On.*|Depends.*)[[:space:]]*:/ { in_deps=1; sub(/^.*:[[:space:]]*/, ""); print; next } /^[^[:space:]]/ { in_deps=0 } in_deps { print }' | tr -s ' ' '\n' | sed '/^$/d; s/[<>=].*//' | sort -u > output.txt
Name            : foo
Version         : 1.0
Description     : Bar
Architecture    : x86_64
Depends On x86_64: glibc>=2.0  gcc-libs=1.0
                   libcurl
                   zlib
Optional Deps   : python
INPUT
if cmp -s output.txt <(echo -e "gcc-libs\nglibc\nlibcurl\nzlib"); then
    echo "Multiline dependency parsing test passed."
    rm output.txt
else
    echo "Multiline dependency parsing test failed. Output:"
    cat output.txt
    rm output.txt
    # Return non-zero code on failure to block CI pipelines
    false
fi
