#!/usr/bin/env bash
set -euo pipefail

repo_root=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )
cd "${repo_root}"

docker build \
       --secret id=CACHIX_CACHE_NAME \
       --secret id=CACHIX_AUTH_TOKEN \
       --progress plain \
       .
