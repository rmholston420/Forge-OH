#!/usr/bin/env bash
# 6-4c-patch-schema-inspect.sh
# Fetch agent-server's OpenAPI PATCH /api/conversations/{id} schema so
# we know exactly what fields are mutable.
#
# Previous version piped curl → python and lost visibility when curl
# failed silently. This version fetches to disk first.

set -uo pipefail
AS="http://127.0.0.1:8090"

echo "=== 0. Fetch OpenAPI (try several likely paths) ==="
tmp=/tmp/6-4c-openapi.json
: > "$tmp"
for url in "$AS/openapi.json" "$AS/api/openapi.json" "$AS/docs/openapi.json" "$AS/api/v1/openapi.json"; do
  code=$(curl -sS -o "$tmp" -w '%{http_code}' "$url" 2>/dev/null || echo err)
  bytes=$(wc -c < "$tmp" 2>/dev/null || echo 0)
  echo "  $url → http=$code bytes=$bytes"
  if [[ "$code" == "200" && "$bytes" -gt 100 ]]; then
    echo "  ✓ using $url"
    break
  fi
done

echo
echo "=== 1. Sanity check the fetched file ==="
head -c 200 "$tmp"; echo
python3 -c "
import json
d = json.load(open('$tmp'))
print()
print('title:', d.get('info',{}).get('title'))
print('paths:', len(d.get('paths',{})))
"

echo
echo "=== 2. PATCH /api/conversations/{conversation_id} schema ==="
python3 - "$tmp" <<'PY'
import json, sys
spec = json.load(open(sys.argv[1]))
paths = spec.get("paths", {})
op = paths.get("/api/conversations/{conversation_id}", {}).get("patch", {})

print("summary:      ", op.get("summary"))
print("description:  ", (op.get("description") or "")[:400])
print("operationId:  ", op.get("operationId"))
print()

body = op.get("requestBody", {}).get("content", {}).get("application/json", {})
ref = body.get("schema", {}).get("$ref")
print("request body $ref:", ref)

schemas = (spec.get("components") or {}).get("schemas", {})
def resolve(ref):
    if not ref:
        return None
    return schemas.get(ref.split("/")[-1])

if ref:
    name = ref.split("/")[-1]
    schema = resolve(ref)
    print()
    print(f"=== resolved: {name} ===")
    print("required:", schema.get("required"))
    props = schema.get("properties", {})
    print("properties (keys):", list(props.keys()))
    print()
    for k, v in props.items():
        r = v.get("$ref") or v.get("type") or v.get("anyOf") or v.get("allOf") or v
        print(f"  {k}: {json.dumps(r)[:180]}")

print()
print("=== 3. Any schema whose name contains 'Update'/'Patch'/'Mutable'? ===")
for n in sorted(schemas):
    low = n.lower()
    if any(t in low for t in ("update","patch","mutable","edit")):
        s = schemas[n]
        print(f"  {n}: props={list((s.get('properties') or {}).keys())}")

print()
print("=== 4. Where does 'working_dir' appear in schemas? ===")
def walk(name, obj, path=""):
    if isinstance(obj, dict):
        for k,v in obj.items():
            np = f"{path}.{k}" if path else k
            if k == name:
                print(f"    {np} = {json.dumps(v)[:150]}")
            walk(name, v, np)
    elif isinstance(obj, list):
        for i,v in enumerate(obj):
            walk(name, v, f"{path}[{i}]")
walk("working_dir", schemas)

print()
print("=== 5. Where does 'workspace' appear in the PATCH schema tree? ===")
if ref:
    walk("workspace", resolve(ref))
PY
