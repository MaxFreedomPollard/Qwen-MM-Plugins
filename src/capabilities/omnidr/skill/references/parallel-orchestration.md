# Parallel readers and host adaptation

Use available, authorized native agents; do not implement another agent loop.
Respect host permissions/concurrency. Keep at most four assignments active unless
explicitly supported otherwise; release finished slots between batches. Batch task
bookkeeping and launch independent readers together. Pending work is not evidence.

Media readers can take several minutes. Keep their task IDs and wait for completion;
do not cancel and replace them merely because results are not immediate. If an
assignment must change, stop it explicitly, confirm termination and inventory saved
passes before replacing it. Resume matching outputs without repeating successful ASR.
Distinguish an explicitly requested task cancellation from a permission refusal using
the recorded task ID and result; cancellation never overrides a separate refusal.

## Native orchestration

Keep bulk source text in reader contexts. Readers consume long texts in bounded
chunks, saving detailed notes and exact supporting passages; return a short findings
index with paths and gaps. The author reads notes and needed excerpts, integrates
the batch, then continues. Do not dump raw HTML or reread entire sources after
compaction. Preserve a `_work/` handoff with completed evidence, pending task IDs and
next report edits. Full-source reading remains mandatory; a preview is not coverage.
This does not permit cached evidence to replace a stopped independent reopen.

1. Plan with `omnidr_plan_video`. Launch one video-reader per ≤300-second source job,
   with the same original, exact interval, focus and distinct `_work/source/clip-N/`.
2. Merge grounded results in source-time order, retain reading.json paths and reuse
   transcripts; never retranscribe the whole source. Save the source checkpoint.
3. Assign priority anchors to anchor-researchers with grounded observations, the
   question, runtime constraints and distinct `_work/anchors/A#/` destinations.
   Include inspected crops/object descriptions for visual anchors. The main author
   owns report-wide floors.
4. Each downloaded related video gets a video-reader over the whole file (its tool
   parallelizes long files). Each important document gets a doc-reader with question
   and scope. Downloads alone are not completed readings.
5. Give a fresh synthesis-reviewer the question, draft and permitted saved findings;
   resolve its consequential editorial gaps before freezing claims. It does not replace
   the fact-checker and must not reopen sources or reconstruct stopped readings.
6. Freeze every compare/timeliness claim, including segment-level ones, then launch
   a fresh fact-checker with only its isolated brief, URLs, date, destination and
   mandatory constraints. Exclude author history/rationale; Codex: fork_turns="none".

Claude discovers the plugin's `agents/` directory. Other hosts use the same role
instructions linked below:

- [video-reader](../../agents/video-reader.md)
- [anchor-researcher](../../agents/anchor-researcher.md)
- [doc-reader](../../agents/doc-reader.md)
- [synthesis-reviewer](../../agents/synthesis-reviewer.md)
- [fact-checker](../../agents/fact-checker.md)

Do not assume Claude Agent/Workflow APIs exist on Codex. If the named anchor
role is unavailable, give a generic agent its full reference. Workers must not invoke
the top-level Skill or delegate again: that duplicates the whole research workflow.
The author owns concurrency, source IDs, data.js, the ledger and integration. Pass
absolute inputs and distinct absolute output paths inside the report; host and tool
working directories may differ. Use relative paths in data/ledger. Return saved paths
and pending task IDs without waiting for others. Integrate each batch before expanding.

## Hosts without native subagents

A host/thread error creating a reader permits the main-agent/tool-pool path for an
otherwise permitted task. An approval denial stops the dependent action instead.
Call `omnidr_read_video` once per whole source. Its bounded pool overlaps visual/ASR
jobs across 300-second intervals and preserves successful passes. The author reads
and reconciles results. Independent searches/downloads can overlap via shell tools.
Reopen sources for inline checks; record method="self-check" and weaker independence,
never an invented reviewer.

## Equivalent shell adapter

If MCP is unavailable, use the same installed implementation:

```bash
python -m qwen_mm_plugins_omnidr.invoke omnidr_read_video --schema
python -m qwen_mm_plugins_omnidr.invoke omnidr_read_video \
  --arguments-file /absolute/path/read-video.json
```

```json
{
  "file_path": "/absolute/path/video.mp4",
  "output_dir": "/absolute/path/report/_work/source",
  "question": "The user's research focus",
  "jobs": 8
}
```

Configure credentials externally. Inspect TOOL_NAME --schema first; report inspection
and validation use project_dir. The adapter shares MCP validation/backend and returns
text/JSON only. Wait for background jobs and check their success explicitly.
