#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
schema="$root/frontend/openapi.json"

uv run --directory "$root/backend" python scripts/export_openapi.py > "$schema"
pnpm --dir "$root/tools/openapi-gen" exec openapi-typescript "$schema" -o "$root/frontend/src/api/schema.d.ts"
rm "$schema"
