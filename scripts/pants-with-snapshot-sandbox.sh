#!/usr/bin/env bash
# Test harness for updating test snapshots courtesy of:
# https://github.com/pantsbuild/pants/issues/11622#issuecomment-1308009408

# FIXME: https://github.com/pantsbuild/pants/issues/11622 see backend/conftest.py
set -euo pipefail

# ensure we operate from the root directory
repo_root=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )
cd "${repo_root}"

# use a 'fixed' path based on the current repo: there's generally only one pants invocation at a
# time in a given directory, and a fixed path gives more chance for cache hits, to avoid rerunning
# all tests every time.
tmpdir="/tmp/pants-snapshot-hack${repo_root}"
# ensure we're starting fresh:
rm -rf "$tmpdir"
mkdir -p "$tmpdir"

copy_snapshots() {
    # `copy_snapshots src dst` copies the __snapshots__ subdirectories in src into dst, preserving
    # the directory structure. dst's __snapshots__ directories become an exact copy of src: files
    # within existing __snapshots__ directories in dst are deleted if they're not in the
    # corresponding spot in src.
    src="$1"
    dst="$2"
    (
        cd "$src"
        find . -name '__snapshots__' -type d
    ) | rsync --verbose --recursive --archive --delete --files-from=- "$src" "$dst"
}

copy_snapshots tests "$tmpdir/tests"

exit_code=0
PANTS_WITH_SNAPSHOTS_HACK_DIR="$tmpdir" ./pants "$@" || exit_code="$?"

copy_snapshots "$tmpdir/tests" tests

exit "$exit_code"
