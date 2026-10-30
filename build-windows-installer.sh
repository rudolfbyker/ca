#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 2 ]]; then
  echo "Usage: $0 ROOT.pem OUTPUT.exe" >&2
  exit 2
fi
source_dir=$(cd -- "$(dirname -- "$0")/windows-installer" && pwd)
output=$(realpath -m -- "$2")
build_dir=$(mktemp -d)
trap 'rm -rf -- "$build_dir"' EXIT
cp -- "$source_dir"/*.go "$source_dir/go.mod" "$build_dir/"
cp -- "$1" "$build_dir/root.pem"
# Validation runs before compilation; no private keys are embedded.
(cd "$build_dir" && GOWORK=off go test ./...)
(cd "$build_dir" && GOWORK=off GOOS=windows GOARCH=amd64 CGO_ENABLED=0 \
  go build -trimpath -ldflags='-H=windowsgui -s -w' -o "$output" .)
if [[ ${BUILD_WINDOWS_TESTS:-0} == 1 ]]; then
  (cd "$build_dir" && GOWORK=off GOOS=windows GOARCH=amd64 CGO_ENABLED=0 \
    go test -c -o "${output%.exe}-test.exe" .)
fi
printf 'Created %s\n' "$output"
