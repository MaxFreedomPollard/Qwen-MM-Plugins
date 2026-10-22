# Review and delivery evidence

Check every compare/timeliness insight at both levels. Start native fact-checkers
without author history (Codex: `fork_turns="none"`). Without agents, reopen sources
inline and disclose weaker independence.
SUPPORTED requires two independent sources and at least one saved quote. Another
source may use an inspected, unquotable screenshot; unreadable pages cannot support
claims. Rewrite/remove REFUTED claims or replace UNREACHABLE evidence, then recheck.
Finalize wording and YYYY-MM-DD dates first: later edits invalidate the review hash.

`inspect_omnidr_report` lists `claims_for_review` with locations and content hashes.
For each assignment, call it with `review_location="insights/0"` (or the listed
segment-level location). Save the returned brief at a separate work path. Give the
reviewer that brief, today's date, its absolute output directory and mandatory constraints.
The brief contains only the current claim, table, hash and cited URLs. Do not send
`data.js`, adjacent claims, author summaries or hints toward a desired verdict.
Reviewers reopen the sources and return findings for this frozen wording; they do
not consult the report for newer wording. If it changes, generate a fresh brief and
review. `authoring_diagnostics.claims` locates stale/missing reviews without changing
them. Hashes bind wording, not factual truth or reviewer independence.

Keep a `_work/research-review.json` ledger with the following shape. Replace the example
paths/identities with actual artifacts; do not copy the example as completed evidence.

```json
{
  "main_reader": "report-author",
  "subagents_available": true,
  "source_readings": ["_work/source/clip-0/reading.json"],
  "primary_readings": [
    {
      "source_id": "S6",
      "reader": "doc-reader-6",
      "scope": "full",
      "source_sha256": "hash of the saved original",
      "notes": "_work/S6-reader.md",
      "page_reads": ["_assets/docs/S6.txt.reading.json"]
    }
  ],
  "visual_anchors": [
    {
      "anchor_id": "A1",
      "crop": "anchors/A1-chart.png",
      "inspected": true,
      "identification_sources": ["S9"]
    }
  ],
  "claims": [
    {
      "location": "insights/0",
      "claim_sha256": "current hash from inspect_omnidr_report",
      "method": "independent",
      "reviewer": "fact-checker-1",
      "verdict": "SUPPORTED",
      "opened_sources": ["S1", "S2"],
      "notes": "_work/reviews/insight-0.md"
    }
  ],
  "render_review": {
    "screenshot": "_work/final.png",
    "images": true,
    "playback": true,
    "bidirectional_seeking": true,
    "citations": true,
    "legibility": true
  }
}
```

Primary readings require `research[].primary=true`, actual publisher/author, full notes
and a matching original-file hash. PDF records must cover every page; full web/text
reading is explicitly attested by its reader. A PDF record alone does not show that its
figures were understood: the doc-reader notes must address them where relevant.

Crops need the tool's `metadata_path` (legacy `<crop>.json` also works), a segment image reference, and
image-search identification sources. If the video truly has no identifiable objects,
record `no_identifiable_objects_reason` rather than fabricating a crop.

Without native subagents, use `subagents_available=false`, each claim's
`method="self-check"`, and a `review_limitation` explaining that sources were reopened
by the author rather than an independent reviewer. Use this fallback only when the
host cannot run independent agents.

`validate_omnidr_report(stage="structure")` supports incremental authoring.
`stage="delivery"` additionally checks 25 sources, five fully read videos on two
platforms, three primary readings, three publishers per anchor, complete main-source
visual/ASR coverage, used crops, current review records and recorded browser checks.
A structural pass never marks `delivery_ready`. Even a delivery pass is a consistency
check over recorded evidence, not a judge of factual truth or honest reviewer identity.
