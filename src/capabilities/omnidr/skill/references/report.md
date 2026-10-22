# Report data and delivery

`prepare_omnidr_report` creates a portable directory with browser-ready source media,
the existing OmniDR renderer, its data schema and an empty draft. It refuses to overwrite
an existing directory. Resume by reading the files, not by initializing again.

```text
report/
  index.html
  styles.css
  js/{app.js,link.js,data.schema.js,data.js}
  media/source.mp4
  img/                       segment frames
  anchors/                   object and citation crops
  _assets/{videos,images,docs}/
  _work/                     reading manifests, transcripts, notes and research-review.json
  omnidr-project.json        source fingerprint and timeline
  TOOLS_USED.md              provenance and review notes
```

Serialize `window.DATA = <JSON>;` with `json.dumps`/`JSON.stringify`. No executable JS,
comments, templates, functions or trailing commas. `js/data.schema.js` is a reference;
do not copy it over data.js. Edit data/evidence only; retain the renderer.

Essential shape:

- `meta`: theme `t01`–`t20`, subject category and language `zh` or `en`.
- `video`: title, `media/source.mp4`, positive source duration and optional local poster.
- `summary`: subject-facing overview.
- `segments`: source-absolute `start/end`, title, keyframe, ordered caption blocks,
  source IDs and optional segment-level insights.
- `anchors`: planning reasons tied to real segment IDs.
- `research`: opened sources with IDs, canonical URLs, findings, `anchorId`, and local
  `media` paths and `publisher`. Video entries use `perception` for the complete
  reading.json manifest; primary text sources have `primary: true`.
- `insights`: source-backed comparisons, causes, context and dated corrections. Both
  top-level and segment-level comparisons/corrections require two sources and evidence.

Use inline `[S#]` citations. Caption blocks support text, image, flow, mindmap and static
SVG; insight comparison tables use the schema's table structure. Explain the subject
on the page. Keep workflow steps, research quotas and tool diagnostics in `TOOLS_USED.md`.

## Illustrated notes and built-in diagrams

Use a representative frame inside each segment's interval where permitted. Use each
image once, as a keyframe or caption block; prefer a caption block for explicit frame
time and credits. The renderer suppresses repeated images. Use the extractor's returned
**actual timestamp**, since sharp-frame selection may move away from the requested
instant. Put that time in the caption, e.g. `02:35 — the observed control setting`.
Inspect the crop/frame you will publish. A missing or refused visual interval remains
a disclosed gap; do not move an unrelated earlier image into it to fill the layout.

Interleave prose, frames and object crops. Reconcile saved image assets with their
actual report positions; an internal anchor reference does not display a crop.
Keep review-only frames and superseded assets with provenance under `_work/`, not
delivery image folders. Preserve useful evidence; never delete it to improve a count.
Identify external illustrations with source citations. Give segments content-specific
titles, including opening/closing material, without inventing content to expand a title.

Built-in `caption` blocks:

```json
{"type":"flow","title":"How the outcome follows","steps":["Observed condition [S1]","Supported mechanism [S2]","Practical consequence [S1][S2]"]}
```

```json
{"type":"mindmap","root":"Decision criteria","branches":[{"label":"Performance","items":["Relevant measured condition [S1]"]},{"label":"Constraints","items":["Documented limitation [S2]"]}]}
```

Replace the example content with actual findings and existing source IDs. Use a flow
for a causal chain or decision sequence, a mind map for genuinely branching factors,
and a comparison table for parallel alternatives. A structured block should clarify
the subject, not diagram the research workflow. SVG charts are also supported; supply
static, self-contained markup with cited data in a `type: "svg"` block.
Use image blocks for inspected raster frames/photos. Do not invent data or require
a separate diagram service. Read the generated schema for the table format.

`authoring_diagnostics.presentation` lists unplaced images, generic titles, repeated/
misaligned frames and missing caption times/illustrations without reading pixels. A zero
`structured_diagram_blocks` count suggests considering a useful diagram, not filler.

All media and evidence paths must stay inside the report and refer to regular local
files. Copy artifacts rather than linking to temporary files or private source folders.
Exclude authentication data, cookie files, environment files and model weights.

Run `validate_omnidr_report(stage="structure")` after each substantial authoring pass;
run `stage="delivery"` before delivery using the ledger in [review.md](review.md). It
rejects incomplete drafts, invalid citations and anchors, missing media, unbacked
comparison/correction quotes, altered renderer files, and accidental credential files.
A structural pass returns `structure_valid` and never marks `delivery_ready`. A delivery
pass also checks the research requirements and recorded review, but is not a claim of
independently verified research quality.

Use `omnidr_screenshot`, then inspect the image. Test playback, seeking both ways,
citations, images and language/theme in both panes. Run custom Playwright checks
with the Python interpreter used by the MCP server. Open the absolute `index.html` file URI.
HTTP needs Range/206; plain `python -m http.server` can break seeking.
Record measured play/seek results; exit 0 alone is not a pass. Expand details
before clicking a visible citation. Page checks do not establish factual support.
