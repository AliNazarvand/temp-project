# SIM800 family datasheet extraction bundle

**Extraction date:** 2026-10-14  
**Repository:** https://github.com/AliNazarvand/Package-Datasheet-sim800  
**Snapshot:** `9d1175b0853f8811a3a76d84219dedac151c7f7f`

## Contents

- `sim800_datasheets.json` — consolidated machine-readable record for all nine requested models plus the shared AT-command catalog.
- `modules/<model>.json` — model-separated records for SIM800L, SIM800C, SIM808, SIM868, SIM800A, SIM800F, SIM800H, SIM800, and SIM800C-DS.
- `shared_at_command_catalog.json` — source-faithful catalog of 340 detailed AT-command sections from V1.12 and recorded edition-comparison material for V1.01/V1.10/V1.12.
- `specs.csv`, `at_commands.csv`, `tests.csv` — normalized tabular exports with source PDF and physical page columns.
- `summary.md` — compact cross-model comparison table.
- `validation_report.md` — missing data, ambiguities, edition differences, source scope, and citation audit.
- `source_manifest.json` — source PDF names, page counts, SHA-256 hashes, and repository snapshot.
- `output_manifest.json` — byte counts and SHA-256 hashes for output files (excluding itself).

## Citation and null conventions

Citations use 1-based **physical PDF page positions**, not printed page labels. Each PDF page was extracted to text; technical claims are tied to a specific source PDF and page. A `null`, empty value, or missing-data entry means the supplied source did not establish that fact; it must not be interpreted as proof the module lacks the capability. Graphical diagrams and multi-column tables can lose visual relationships in text extraction; uncertainty is called out in the per-module `ambiguities` fields and validation report.

AT commands are cataloged from the **family** manual and are not automatically asserted as supported by every model. The extraction preserves source forms/raw blocks where layout parsing is uncertain. In particular, legacy V1.01/V1.10 presence detection for `AT+CEER` may be incomplete because of split heading formatting; the V1.12 detailed catalog is unaffected. See the catalog’s `extraction_notes` and `version_differences`.

## Reproducibility and date-versioning

The source snapshot, PDF page counts, and SHA-256 hashes are included in `source_manifest.json`. Outputs are placed under `2026-10-14/` so a subsequent extraction can be stored in a new dated folder and compared without overwriting this version. No technical values were backfilled from outside sources.
