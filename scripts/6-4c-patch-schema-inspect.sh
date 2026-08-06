#!/usr/bin/env bash
# 6-4c-patch-schema-inspect.sh
# Fetch agent-server's OpenAPI PATCH /api/conversations/{id} schema so
# we know exactly what fields are mutable, before drawing a verdict.

set -uo pipefail
AS="http://127.0.0.1:8090"

echo "=== PATCH /api/conversations/{conversation_id} schema ==="
curl -sf "$AS/openapi.json" | python3 - <<'PY'
import json, sys
spec = json.load(sys.stdin)
paths = spec.get("paths", {})
op = paths.get("/api/conversations/{conversation_id}", {}).get("patch", {})

print("summary:      ", op.get("summary"))
print("description:  ", (op.get("description") or "")[:400])
print("operationId:  ", op.get("operationId"))
print()

body = op.get("requestBody", {}).get("content", {}).get("application/json", {})
ref = body.get("schema", {}).get("$ref")
print("request body $ref:", ref)

# Resolve the ref
schemas = (spec.get("components") or {}).get("schemas", {})
if ref:
    name = ref.split("/")[-1]
    schema = schemas.get(name, {})
    print()
    print(f"=== resolved schema: {name} ===")
    print(json.dumps(schema, indent=2)[:3000])

print()
print("=== also: does the schema mention workspace/working_dir? ===")
raw = json.dumps(schemas).lower()
print("  'working_dir' occurs:", raw.count("working_dir"), "times")
print("  'workspace' occurs:  ", raw.count("workspace"), "times")

# Show anything that has 'working_dir' in the property tree
def find(name, obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            new = f"{path}.{k}" if path else k
            if k == name:
                print(f"    {new} = {json.dumps(v)[:150]}")
            find(name, v, new)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            find(name, v, f"{path}[{i}]")

print()
print("=== schema locations containing 'working_dir' ===")
find("working_dir", schemas)

print()
print("=== schemas that reference workspace mutation ===")
for n, s in schemas.items():
    if "patch" in n.lower() or "update" in n.lower():
        props = list((s.get("properties") or {}).keys())
        print(f"  {n}: props={props}")
PY
