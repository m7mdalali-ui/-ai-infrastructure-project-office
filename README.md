# AI Infrastructure Project Office

Consultant-side AI Project Office for infrastructure supervision. Phase 1 establishes the deterministic foundation of the **Senior Planning Engineer Agent**.

## Phase 1 implemented foundation
- Normalized schedule model for activities, relationships, calendars and source metadata.
- Importers for P6 XER, P6 XML, Microsoft Project XML and explicitly mapped Excel.
- Native MPP is intentionally **not** claimed; export to Microsoft Project XML.
- Network validation for broken/self/duplicate relationships, invalid progress/dates/durations, open ends and isolated activities.
- Deterministic CPM supporting FS/SS/FF/SF and positive/negative lag.
- Critical and near-critical identification.
- Structured programme review with Data Exceptions, recommendation and mandatory Human Decision flag.
- Tests covering core network/validation behavior.

## Governance
The engine must not invent dates, quantities, resources, rates, approvals, progress or contractual facts. Missing evidence is a Data Exception. AI recommendations never replace Engineer/Resident Engineer approval.

## Install/test
`python -m pip install -e ".[test]"`
`pytest -q`

## Current limitations
This is Phase 1, not the complete Senior Planning Engineer Agent. Calendar-aware working-time CPM, full P6 resource/cost loading, progress credibility, recovery/acceleration, monthly report review, EOT/TIA/windows analysis, cross-agent handoffs and UI integration are later phases. P6/MSP XML mappings are intentionally conservative and require expansion against real exports.

## Next
Phase 2 should harden real P6 imports, calendars, constraints, milestones and activity codes, then validate against representative real project files before adding recovery/EOT logic.
