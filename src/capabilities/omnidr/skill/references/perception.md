# Video perception and timestamp contract

Read consecutive ≤300-second ranges with dense visual captions and concurrent ASR.
Source ranges avoid stream-copy drift. New plans avoid subsecond tails; legacy ranges
and successful passes stay unchanged. A failed legacy tail visual may add one preceding
second as `visual_interval`; ASR is unchanged. Coverage checks use actual ranges.

`omnidr_read_video` saves `reading-plan.json`, per-clip `.visual.json`/`.tr.json`/`.tr.txt`,
merged `transcript.txt` and `reading.json`, retaining hashes/intervals. `incomplete`
means gaps remain. Resume with the same directory/source/range: reuse successes;
retry only missing, non-refused passes. Narrow `omnidr_read_media` follow-ups avoid
repeating ASR.

Inside a prepared report, new ASR jobs also check `_work` for overlapping successful
`.tr.json` results of the same source or registered alias. Changing directories cannot
repeat that speech pass. Reuse its transcript and use `omnidr_read_media(mode="frames")`
for visual follow-ups; do not build new ASR jobs to fill a visual gap. This check does
not approve the cached text or bypass any stop. Standalone reads retain directory-local reuse.

Use one source across readers. Originals/transcodes share time, not hashes; resume
matching plans without mixing passes or rewriting hashes.

Bind stops to verified source/derivative identity, modality and interval; equal
timestamps do not identify sources. Preserve unresolved identities and the shared journal.
A preflight block does not expand an existing stop to the batch. Keep that gap.
For other permitted, non-overlapping visual ranges use `omnidr_read_media(mode="frames")`
and reuse ASR. Check current constraints first; unknown/whole-source stops remain blocked.
Never reconstruct stopped content or retry the parent batch. Stops persist across
crops, copies, directories, readers, models and interfaces. ASR cannot evade stopped
audio/video; visual-only stops do not forbid audio. Pass constraints to all readers
and reviewers, including native tools. Record gaps; partial coverage stays incomplete.

Dense captions include events every 10–20 seconds, OCR/numbers/units, spatial anchors,
uncertainties and representative frames. Reconcile ASR terms/numbers against this evidence.

## Frame detail and context

`omnidr_read_video` defaults to **32 frames/320px per clip**; choose `frames=16..48`
and `frame_height=480` when fast cuts or OCR warrant it. New `.visual.json` files
record requested detail, actual dimensions and decoded timestamps. On resume, these
options affect only missing passes; saved readings keep their detail and bytes.
Older observations without sampling metadata remain unknown, never relabeled.
Use `omnidr_read_media` for a narrow follow-up: 720px requires ≤16 frames.
For saved-frame/page OCR use `mode="image"`: original image bytes are retained unless
an explicit `max_pixels` requests downsampling. Saved observations record actual
`image_size` and the requested budget. Native-video preprocessing still defaults to
200704 pixels per frame; frame sampling uses its separate height ladder.
Return text/paths, not Base64. Sampling can miss brief events; narrow the interval.
Native image viewing is for crop inspection.

All media modes use `QWEN_MM_API_OMNI_MODEL`, separately from the host model.
Leave `model` unset unless an Omni-compatible override was explicitly selected.
Use `frames`/`image` for visual-only checks and `video`/`audio` for audiovisual or speech evidence.

`omnidr_extract_frame` selects the sharpest non-fade among nine frames over 0.8s.
`exact=true` pins time; crops default to exact. Reinspect crops after widening the
window because objects may move. `box_units="pixels"` uses native image coordinates;
`"normalized"` uses 0–1000 image coordinates. Preserve the returned timestamp and
`metadata_path`: prepared reports use
`_work/frame-provenance/<image-relative-path>.json`; standalone images use adjacent
`<image>.json`. Retain both layouts if present, including `_work` and the policy
journal when moving/copying reports.

## Time origins

- Frame observations embed **source-absolute** timestamps; origin is zero.
- Raw `omnidr_read_media(mode="audio"|"video")` model timestamps are clip-relative;
  add `timestamp_origin_seconds` exactly once.
- `omnidr_transcribe` and `omnidr_read_video` transcripts are already **source-absolute**;
  do not add the clip offset again. Transcription can record explicit non-speech/silence;
  absent audio is `no_audio`, not an invented transcript.

Save external manifests under `_work/` and link them in the source's `perception`;
link main-source manifests in `_work/research-review.json.source_readings`.
Full coverage requires visual and ASR files for every interval, not partial observations.

Offline checks must disclose material/gaps; never fabricate model or reader results.
