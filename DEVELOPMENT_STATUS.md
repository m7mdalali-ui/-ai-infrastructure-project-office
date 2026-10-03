# Senior Planning Agent — development status

This is a continuation of the existing Python planning package. V1 is not complete
and the independent calculation engine is not equivalent to Primavera P6.

## Implemented in this block

- Explicit project selection for multi-project XER; scoped tasks, codes,
  assignments, resources and calendars. Duplicate activity codes refused.
- Raw task/calendar/project/table values retained. Physical percent values are
  preserved on the P6 percentage scale. Missing hours/day does not imply 8 hours.
  A missing day conversion is flagged; raw duration hours remain usable.
- Broken relationships retained as unresolved references with source evidence.
- Detailed P6 weekday/shift/exception parsing, OLE exception dates, base calendar
  inheritance, overlap checks and summary/detail conflicts.
- Working-time navigation, signed duration arithmetic and hours-between functions.
- Separate baseline calendar CPM and reconciliation modules. FS/SS/FF/SF with
  signed source-hour lags, explicit lag calendar policy, dated passes, independent
  float, milestone validation, and project-deadline negative float.
- Conservative refusal of unsupported constraints, progressed scheduling, LOE,
  resource-dependent tasks and broken calendars/networks.
- Baseline orchestration now includes validation findings and a proposed review
  disposition. Contractual acceptance and scope completeness remain unverified.
- Update comparison includes calendars, names, actuals, remaining duration,
  constraints and float-path changes. Different project IDs block comparison
  pending explicit project mapping rather than mixing projects.
- Recovery scenarios include current crews, material/workfront/equipment/sequence
  caps, gates, weekly work patterns, elapsed testing time, ceiling, finish and
  latest recoverable production-start date when a capacity ceiling is supplied.
- Monthly variance calculation preserves the source submission and flags conflicts.
- EOT supports a conservative verified single-event scalar calculation; unverified
  evidence and multiple-event net impact are blocked. This is not a delay-analysis
  methodology implementation or a contractual entitlement decision.
- Source-based 7/14/30-day lookahead and controlled-input executive summary.
- API routes for calendar reconciliation, lookahead and executive summary.
- CI triggers main/planning branches, pull requests and manual workflow dispatch.

## Executed validation

`python3 -m pytest -q` — 83 passed, 0 failed, 0 skipped at this checkpoint.
`python3 -m compileall -q src` and `git diff --check` were also executed.
Synthetic tests are committed; proprietary reference schedules are not.

Private reference execution exercised table-count preservation, source task and
lag-hour preservation, all calendars, all activity status checks and the baseline
review route for each isolated dataset. Full dated CPM was refused because those
files contain unsupported scheduling semantics; no finish/float equivalence is
claimed.

## Limitations and next block

1. Implement P6 constraints, actual/remaining scheduling, data-date behavior, LOE
   and resource-dependent semantics, then reconcile real schedules independently.
2. Add a configurable source-scheduling-options model; do not guess lag policy,
   float policy, retained logic or progress override.
3. Complete contractual milestones/scope/procurement/authority review using supplied
   requirements and evidence. Source zero float is not a demonstrated critical path.
4. Upgrade recovery to calendar-based daily supply/inventory, workfront and sequence
   simulation. Current recovery is uniform-rate planning, not batch logistics.
5. Complete progress weighting, forecast reconciliation, report document extraction,
   EOT window/network methods, controlled knowledge governance and project-scoped
   authenticated persistence.
6. Add evidence-led conversational Q&A with a replaceable LLM adapter. No language
   model is connected in this block and the API is a Python function, not an HTTP
   upload service.

The legacy numeric CPM remains available for existing tests and is labelled
non-calendar-aware. The new dated engine is explicitly invoked; source P6 values
are never overwritten by it. Calendar datetimes are naive project-local wall time;
DST, overnight shifts without explicit midnight splitting and unrecognized P6
calendar syntax are unsupported. Calendar interval scans are bounded to 100 years.
Human review is required for all significant conclusions.
