from pathlib import Path

path = Path("/app/app/services/beta_readiness.py")
source = path.read_text()
old = 'EXPECTED_SCHEMA_REVISION = "d7a9b123e5f7"'
new = 'EXPECTED_SCHEMA_REVISION = "e8b0c234f6a8"'

if old not in source:
    raise SystemExit("Expected beta-readiness schema revision marker not found; refusing unsafe patch")

path.write_text(source.replace(old, new, 1))
print("Beta-readiness schema-head patch applied")
