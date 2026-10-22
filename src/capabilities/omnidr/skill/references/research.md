# Research outward from grounded anchors

Use the six anchor categories and research requirements defined in SKILL.md.
Choose anchors from both speech and visible objects, using the readers' candidate
lists before inspecting pixels. Record id, category, why and segmentIds. Useful object
crops include papers/author lists, charts, products/logos, people, art, locations and UI.

For each anchor, search in parallel for facts, independent corroboration, competing
products/events, viewpoints, related videos, and changes since recording. Use real
publisher/author independence: three mirrors of one article remain one source.

## Acquisition and reading

- Web facts: `omnidr_search(kind="web")`, then `omnidr_fetch_source` with
  `engine="auto"` or `"direct"` to save original HTML/PDF/image bytes. `answer` can ask the Omni model
  a focused question from the retrieved page. Use `readable_path` for complete text;
  `path` retains original bytes and may be HTML even with a .md filename. The preview
  is not a full reading. Keep both artifacts and their `.source.json` hash binding.
- Related videos: search `kind="video"` on the web plus direct platform calls with
  `backend="platform", site="bilibili"` and `site="youtube"`. Check cross-platform
  downloads early: search success does not establish download access.
  If a platform is network-unreachable, seek independently published relevant videos
  elsewhere. Actual approval/provider refusals remain stopped. Download with
  `omnidr_download_video`. The Bilibili route uses
  view/playurl APIs and merges DASH audio/video; `page` selects a part. YouTube/generic
  uses yt-dlp and an optional external cookie file. Authentication is never fabricated.
- Confirm the downloaded video's identity: compare the returned platform title,
  part title and uploader with the search result, then verify against actual video
  content. Search titles and filenames can be wrong. Correct mismatches in source
  records; an unrelated video cannot corroborate the requested product or test.
- Every selected video gets its own reader using `omnidr_read_video`, not only ASR.
  Save the canonical watch URL returned at download time, the original media and the
  complete reading manifest. No search URLs, dead placeholder media or thumbnail-only
  summaries count toward the five-video floor.
- Images: use `kind="image"` with the inspected object's description. The MCP search
  tool does not provide reverse image search; perform an actual lookup with an available
  host browser when needed, or record it as incomplete. Keyword matches are not reverse
  lookup results. Local crops are not automatically uploaded. Save originals with direct
  fetch and preserve source pages.
- Papers/reports: use web/academic queries, or fetch the public arXiv API for exact
  titles. Download PDFs, then assign a doc-reader. `omnidr_read_document` extracts and
  renders bounded page ranges. Repeat to the end for the three primary sources;
  inspect important figures, tables and scanned pages with `omnidr_read_media`.
  Keep the generated `.reading.json` metadata for full-page coverage checks.
  Plain .txt/.md and saved HTML can be read fully with the host's file tools; the
  document MCP tool is for PDFs. Save reader notes and the original hash in either case.

## Evidence and synthesis

Fetch/download tools save an adjacent `.source.json` receipt with the public source
URL, artifact hash and retrieval metadata. Inspection lists unintegrated acquisitions;
use this index on resume. Acquisition is not reading or corroboration. Reconcile each
record with the actual content before adding it to the source catalog.

Record S# id, type, title, canonical URL, distilled findings, publisher/author,
`anchorId`, and a saved local `media` copy for every source. `anchorIds` can additionally
link one source to other anchors. Mark authoritative text sources with `primary: true`
and record full doc-reader results in the review ledger. Related videos use `perception`
for their complete reading manifest. Sources with inaccessible content do not count.

Preserve publication/access dates where timeliness matters. Search snippets are leads,
not findings. The report should teach comparisons, causes and dated updates that the
video alone cannot establish. Outside material must outweigh paraphrase, even for a
focused question. Include counterevidence; do not infer facts merely from fluent model
output. Quote support from saved pages, faithful PDF extracts or source-grounded
transcripts, never text authored to justify the conclusion.

Compare/timeliness insights at both levels need two independent sources and at least
one matching saved quote. See review.md for independent checks and unquotable sources.
