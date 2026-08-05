# Rubric — arch.md scoring (0-100)

Score each cell response against `gold/arch.md`. Total = sum of dimensions.

## Dimension A — Correct Decision (30 pts)

- 30: keeps `bff/openhands_client.py`, deletes `bff/services/openhands_client.py`
- 0: any other decision (keeps services shim, proposes rename, proposes merge, proposes keeping both)

**This is a hard gate — if the decision is wrong, the model failed the task regardless of other dimensions. Cap total at 20 pts.**

## Dimension B — Justification Quality (25 pts)

- 25: justification references (a) that `bff/openhands_client.py` is the canonical lifespan-managed client, (b) that `bff/services/openhands_client.py` is a zero-importer shim, AND (c) that keeping the flat file satisfies both the importer graph AND the layering convention (cross-cutting = allowed in bff/*)
- 18: mentions two of the three
- 12: mentions one (typically only the shim-vs-canonical distinction)
- 6: correct decision but justification uses only generic "services layer wins" or "cleanest" reasoning
- 0: justification contradicts the decision or is absent

## Dimension C — Grep Pattern (15 pts)

- 15: grep covers BOTH `bff.services.openhands_client` (dotted) AND `from bff.services import openhands_client` (from-import form); restricted to `.py` files
- 10: covers one form only, restricted to `.py` files
- 5: covers one form only, no file-type restriction
- 0: grep pattern would miss real matches or produce false positives that break the sed

## Dimension D — Sed Rewrite (15 pts)

- 15: sed rewrites BOTH forms (`bff.services.openhands_client` → `bff.openhands_client`, and `from bff.services import openhands_client` → `from bff import openhands_client`); no data loss
- 10: rewrites the dotted form only
- 5: rewrites both forms but with unsafe pattern (e.g. would break relative imports if present)
- 0: sed would corrupt files or miss real matches

## Dimension E — Convention-Grounded Reason (10 pts)

- 10: reason names the actual convention text (cross-cutting concerns in `bff/*.py`) AND ties it to a specific behavior of the kept file (lifespan management, singleton `httpx.AsyncClient`, startup/shutdown wiring)
- 6: names the convention but doesn't tie it to specific behavior
- 3: uses generic "layering" reasoning without citing the specific convention text
- 0: reason is a general preference statement, not convention-grounded

## Dimension F — Format Discipline (5 pts)

- 5: emits exactly the four-part format the task asked for, no extra framing
- 3: emits the four parts plus minor framing
- 0: reorders, merges, or omits any of the four parts

## Scoring Notes

- **Hard gate:** wrong decision = cap at 20 pts
- **Extra credit** (not counted, tiebreak only): cites specific GitHub commit hashes or file line numbers to verify the claim
- **Deduct 5 pts** if the response proposes keeping both files or merging them (this is explicitly forbidden by the task)
