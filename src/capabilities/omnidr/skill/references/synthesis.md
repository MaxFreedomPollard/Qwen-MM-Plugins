# Turn consumed sources into a useful report

Use after reading and before final claim review. Turn evidence into explanations,
comparisons and practical implications; source counts alone do not establish depth.

Before selecting anchors and again on resume, map each distinct part of the user's
question to its answer, saved evidence and report location in `_work/`. A related
discussion is not an answer: preserve requested conditions and explain how evidence
supports the conclusion. Prioritize consequential unanswered parts when assigning
readers. Before review, resolve each part or state the specific remaining uncertainty;
do not fill evidence gaps with assumptions. Keep this working map out of the report.

## Reconcile the source notes before expanding the report

On every resume too, check question-relevant claims against saved original ASR/OCR
and visual observations. Reader summaries and prior verdicts locate evidence;
they cannot verify wording they already paraphrased.

In `_work/`, retain a row per consequential source claim: exact short passage,
source times, artifact path, report wording/location and unresolved discrepancy.
Check numbers, bounds, units, negations, causal links and conditions directly against
these passages before calling a claim faithful. Keep repeated utterances separate.
Use short attributed quotes where wording matters; uncertain ASR stays uncertain.
Restore supported details lost in compression without inventing missing links.

Reuse successful readings; never repeat perception or reopen stopped actions.
Coverage agents receive bounded original evidence and report text, returning gaps
for the author to resolve. Their working map is not a factual-verification verdict.
Keep them separate from claim-only fact-checkers, who never receive the report or
author reasoning. Structural validity alone does not establish source fidelity.

## Extract the evidence that changes the answer

For each chosen research anchor, keep a small working evidence table in `_work/`:

| Question to resolve | Finding and scope | Source / saved passage | Where it belongs |
|---|---|---|---|
| What exactly is being compared? | Official name, definition and generation | Source ID and original passage | Background or comparison |
| Under what conditions does it work? | Measured/specification limits, units and test conditions | Source ID, page or time | Relevant segment and trade-off |
| Why did the observed outcome occur? | Evidence for each causal link; alternatives still possible | Independent findings | Causal explanation |
| What changes the user's decision? | Counterevidence, constraints and remaining uncertainty | Supporting or conflicting sources | Verdict and dated update |

Record unavailable facts as gaps. Preserve supported authority/standard names,
applicability, capacity, units, test conditions and device/version/date. Distinguish
marketing, specification limits, observations and inference; cite derived inputs.
Do not broaden a model-specific fact to its family or substitute another generation.
After synthesizing saved evidence, search narrowly for unresolved consequential gaps.

## Integrate each reader result promptly

On resume and before final synthesis, inspect `authoring_diagnostics.evidence_handoffs`.
Open the permitted saved reader notes, not just the catalog or their prior summaries.
For each, decide which consequential finding belongs in the report and reconcile it
with the original saved passage; then edit the relevant explanation. A citation to
the source does not establish that its findings have been incorporated.

Save the disposition in `_work/synthesis.json` as `{"handoffs": [...]}`. Each entry
has `path`, `notes_sha256` from the inventory, `disposition` (`integrated`,
`out_of_scope` or `blocked`), `report_locations` and a short `reason`. Resolve
`unrecorded` or `notes_changed` entries from their actual content, without turning
every note into report prose. Preserve access stops; inventorying a blocked note
does not authorize reopening it. This is an authoring record, not an independent
review or a new research quota; confirm the report actually contains the findings.

Add each consumed source and its relevant finding promptly. Videos need the canonical
URL, publisher, media and complete `perception` manifest; primary texts need a full
reader record bound to the original file hash. Save reviewer downloads at new paths
to preserve original reading records.

Put `[S#]` beside the supported sentence: catalog summaries and `sources` arrays do
not replace synthesis or identify sentence-level support. Keep unused leads in the
work log; do not pad citations or discard useful evidence to improve a ratio.
Use `authoring_diagnostics` to reconcile unused sources, unintegrated readings and
missing primary-reader records. Inventory entries alone do not establish consumption.

## Fuse findings rather than concatenate summaries

- **Comparison:** organize a table around the user's decision criteria, using the
  same units and conditions where possible. Explain the trade-off and give a verdict
  with its limits. A list of unrelated specifications is not a comparison.
- **Cause:** connect the observed condition, physical or logical mechanism, resulting
  effect and limits. Naming components alone does not explain an outcome. Cite each
  factual link; distinguish plausible explanations from demonstrated causes.
- **Timeliness:** retain the source video's historical context, then state what the
  current evidence establishes as of `YYYY-MM-DD`. A change in a later generation is
  not proof that the original generation gained that capability.

Put local findings beside their segment and cross-cutting decisions in top-level
insights. A narrow question focuses external research while the full source retains
illustrated notes. Add relevant substance, not generic facts to lengthen the report.

## Finish the report before reviewing its final claims

Use a fresh synthesis-reviewer with the question, draft, permitted notes and access
constraints, excluding your completion claims and any evaluation material. Save its
editorial findings under `_work/`. Resolve each consequential finding with an edit,
an evidence-based explanation of why the draft already answers it, or an explicit gap.
Keep this review separate from fact-checkers: it sees the draft and author evidence,
so it cannot establish independent factual support. On short runs, reserve a feasible
portion of the remaining budget for this pass, claim review and delivery checks.

Use `report.md` for distinct frames and diagrams. Settle claims, tables, dates and
citations before independent review. Send each location from
`authoring_diagnostics.claims` needing review with its URLs and mandatory constraints.
Any later claim edit needs a new review; never replace the stored hash to reuse a
stale verdict. Reserve time for integration, review and delivery checks. Stop broad
acquisition when these remain; retain concrete gaps caused by service refusals.
