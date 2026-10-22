"""Local media preparation, perception, and document extraction."""

from __future__ import annotations

import base64
import json
import math
import tempfile
from pathlib import Path

from shared import api_omni, api_openai, omni_media
from shared.image import open_image, smart_resize
from shared.video import extract_frames_by_seeking, get_video_info

from . import config, policy
from .common import InputError, ProviderPolicyError, is_provider_policy_error, local_file, new_output, run
from .project import frame_metadata_paths, probe, sha256


def _audio_part(path):
    source = Path(path)
    if api_omni.b64_len(source.stat().st_size) > api_omni.OMNI_MAX_B64_BYTES:
        raise InputError("Audio exceeds the per-item inline limit; use a shorter interval.")
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    return {
        "type": "input_audio",
        "input_audio": {"data": "data:;base64," + encoded, "format": source.suffix.lstrip(".").lower() or "wav"},
    }


def _audio(file_path, cleanup, start_time, duration, effective_duration):
    budget = api_omni.OMNI_MAX_UPLOAD_BYTES
    if start_time == 0 and duration is None and not api_omni.has_video_stream(file_path):
        if Path(file_path).stat().st_size <= budget:
            return _audio_part(file_path)
    if effective_duration * omni_media.WAV_BYTES_PER_SEC <= budget:
        output = omni_media.temp_file(".wav", prefix="omnidr-audio-")
        cleanup.append(output)
        omni_media.extract_audio(file_path, output, start_time=start_time, duration=effective_duration)
    else:
        output = omni_media.temp_file(".mp3", prefix="omnidr-audio-")
        cleanup.append(output)
        omni_media.fit_audio(file_path, output, budget=budget, start_time=start_time, duration=effective_duration)
    return _audio_part(output)


def _frames_and_audio(file_path, fps, max_pixels, cleanup, start_time, duration):
    audio = None
    if omni_media.has_audio_stream(file_path):
        output = omni_media.temp_file(".mp3", prefix="omnidr-audio-")
        cleanup.append(output)
        omni_media.fit_audio(
            file_path,
            output,
            budget=api_omni.OMNI_MAX_UPLOAD_BYTES,
            duration=duration,
            start_time=start_time,
        )
        audio = _audio_part(output)
    frame_limit = api_omni.OMNI_MAX_B64_FRAMES - int(audio is not None)
    urls, timestamps = omni_media.fit_frames(
        file_path,
        duration,
        min(fps, frame_limit / duration),
        max_pixels,
        omni_media.INLINE_B64_BUDGET,
        start_time=start_time,
    )
    if len(urls) > frame_limit:
        raise InputError("Sampled media exceeds the inline item limit; use a shorter interval.")
    parts = [api_omni.omni_frames_part(urls)]
    if audio is not None:
        parts.append(audio)
    parts.append(omni_media.frames_note(timestamps, duration, audio is not None))
    return parts


def build_media_parts(
    file_path,
    mode,
    fps,
    max_pixels,
    cleanup,
    max_video_sec=None,
    *,
    start_time=0.0,
    duration=None,
    preserve_timestamps=True,
):
    """Build audio/video parts; oversized video uses sampled frames and continuous audio."""
    source = local_file(file_path)
    if mode not in {"audio", "video"}:
        raise InputError("Inline delivery requires audio or video mode.")
    file_path = str(source)
    start_time, duration = omni_media.normalize_local_range(file_path, start_time, duration)
    effective_duration = duration if duration is not None else omni_media.media_duration(file_path)
    if not math.isfinite(effective_duration) or effective_duration <= 0:
        raise InputError("The requested media interval must have a positive finite duration.")
    if mode == "audio" or not api_omni.has_video_stream(file_path):
        return [_audio(file_path, cleanup, start_time, duration, effective_duration)]
    if max_video_sec and effective_duration > max_video_sec:
        return _frames_and_audio(file_path, fps, max_pixels, cleanup, start_time, effective_duration)
    output = omni_media.temp_file(".mp4", prefix="omnidr-video-")
    cleanup.append(output)
    try:
        omni_media.preprocess_video(
            file_path,
            output,
            max_pixels,
            fps=fps,
            max_bytes=api_omni.OMNI_MAX_UPLOAD_BYTES,
            start_time=start_time,
            duration=duration,
            preserve_timestamps=preserve_timestamps,
        )
    except omni_media.InlineBudgetExceeded:
        return _frames_and_audio(file_path, fps, max_pixels, cleanup, start_time, effective_duration)
    return [api_omni.omni_video_part(output, fps=fps, max_pixels=max_pixels)]


def perceive(arguments: dict) -> dict:
    path = local_file(arguments["file_path"])
    mode = arguments["mode"]
    prompt = arguments["prompt"]
    output = None
    if arguments.get("output_path"):
        output = new_output(arguments["output_path"])
    start = arguments.get("start_time", 0.0)
    end = arguments.get("end_time")
    image_budget = arguments.get("max_pixels")
    pixels = image_budget if image_budget is not None else 200704
    asr = arguments.get("_asr", False)
    if asr and mode != "audio":
        raise InputError("ASR requires audio mode.")
    cleanup: list[str] = []
    if mode == "image":
        if start or end is not None:
            raise InputError("Time ranges apply to video or audio, not still images.")
        policy.check(path, mode, None)
        with open_image(str(path)) as image:
            w, h = image.size
            if image_budget is None or w * h <= image_budget:
                parts = [api_openai.encode_image_source(str(path), allow_upload=False)]
            else:
                h, w = smart_resize(h, w, 32 * 32, image_budget)
                parts = [api_openai.encode_image_source(image.resize((w, h)))]
        interval = None
    else:
        info = probe(path)
        end = min(end if end is not None else info["duration"], info["duration"])
        if start >= end:
            raise InputError("The requested time range is empty or outside the media.")
        if end - start > 600:
            raise InputError("Inspect at most 600 seconds per call; use consecutive ranges with overlap when needed.")
        interval = [start, end]
        policy.check(path, mode, interval)
        if mode == "frames":
            if not any(s.get("codec_type") == "video" for s in info["streams"]):
                raise InputError("Frames mode requires a video stream.")
            video_info = get_video_info(str(path))
            count = arguments.get("frames", 32)
            height = arguments.get("frame_height", 320)
            if height == 720 and count > 16:
                raise InputError("Use at most 16 frames on a narrow 720p inspection pass.")
            h = min(height, video_info["height"])
            w = max(2, round(video_info["width"] * h / video_info["height"]))
            # Audio padding may extend past the final decodable video frame.
            last_frame = max(start, video_info["duration"] - 1 / video_info["native_fps"])
            times = [min(start + (end - start) * i / count, last_frame) for i in range(count)]
            extracted = extract_frames_by_seeking(str(path), times, h, w)
            if not extracted:
                raise InputError("No video frames could be decoded.")
            parts = []
            for timestamp, encoded in extracted:
                parts.extend(
                    [
                        {"type": "text", "text": f"Source timestamp: {timestamp:.3f} seconds."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
                    ]
                )
        elif mode == "audio" and not any(s.get("codec_type") == "audio" for s in info["streams"]):
            raise InputError("The media has no audio stream.")
    try:
        base_url, api_key, model = config.omni_settings(arguments.get("model"))
        if mode in {"audio", "video"}:
            parts = build_media_parts(
                str(path),
                mode,
                1.0,
                pixels,
                cleanup,
                api_omni.omni_video_max_sec(model),
                start_time=start,
                duration=end - start,
                preserve_timestamps=True,
            )
        text, _ = config.call_omni(
            base_url=base_url,
            api_key=api_key,
            model=model,
            **config.chat_options([*parts, {"type": "text", "text": prompt}], asr),
        )
        if not text or not text.strip():
            raise InputError("The model returned no observations; this range has not been inspected.")
        result = {
            "status": "observed",
            "mode": mode,
            "backend": "shared",
            "text": text,
            "model": model,
            "source_interval": interval,
            "timestamp_origin_seconds": start if mode in {"audio", "video"} else 0,
            "source_sha256": sha256(path),
        }
        if mode == "image":
            result.update(image_size=[w, h], max_pixels=image_budget)
        elif mode == "frames":
            result["sampling"] = {
                "requested_frames": count,
                "requested_height": height,
                "height": h,
                "width": w,
                "timestamps": [timestamp for timestamp, _ in extracted],
            }
        if output is not None:
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            result["evidence_path"] = str(output)
        return result
    except Exception as exc:
        if is_provider_policy_error(exc):
            try:
                policy.remember(path, mode, interval)
            except OSError:
                raise ProviderPolicyError(journal_failed=True) from None
            raise ProviderPolicyError() from None
        raise
    finally:
        omni_media.cleanup_files(cleanup)


def extract_frame(
    video_path: str,
    timestamp: float,
    output_path: str,
    box: list[float] | None,
    window: float | None = None,
    candidates: int = 9,
    exact: bool = False,
    box_units: str = "normalized",
) -> dict:
    source = local_file(video_path)
    info = probe(source)
    if timestamp >= info["duration"]:
        raise InputError("Frame timestamp must lie within the video duration.")
    span = 0 if exact else (window if window is not None else (0 if box else 0.8))
    policy.check(source, "frames", [timestamp - span / 2, timestamp + span / 2])
    target = new_output(output_path)
    if target.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise InputError("Frame output must use .jpg, .jpeg or .png.")
    if box and (
        len(box) != 4
        or not (0 <= box[0] < box[2] and 0 <= box[1] < box[3])
        or (box_units == "normalized" and max(box) > 1000)
    ):
        raise InputError("Box must be [left, top, right, bottom] in 0–1000 coordinates with positive area.")
    records = frame_metadata_paths(target)
    if any(path.exists() or path.is_symlink() for path in records):
        raise InputError("Frame metadata already exists; choose a new output path.")
    metadata_path = new_output(str(records[0]))
    with tempfile.TemporaryDirectory(prefix="omnidr-frame-") as directory:
        from PIL import ImageFilter, ImageStat

        times = (
            [timestamp]
            if span <= 0 or candidates <= 1
            else [
                max(0, min(info["duration"] - 0.001, timestamp - span / 2 + span * i / (candidates - 1)))
                for i in range(candidates)
            ]
        )
        scored = []
        for i, time in enumerate(times):
            frame = Path(directory) / f"frame-{i}.png"
            run(
                ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(time), "-i", str(source), "-frames:v", "1", str(frame)]
            )
            if not frame.exists():
                continue
            with open_image(str(frame)) as image:
                gray = image.convert("L")
                gray.thumbnail((320, 320))
                stats = ImageStat.Stat(gray)
                faded = stats.stddev[0] < 12 or stats.mean[0] < 16 or stats.mean[0] > 240
                sharpness = (
                    ImageStat.Stat(
                        gray.filter(ImageFilter.Kernel((3, 3), [0, -1, 0, -1, 4, -1, 0, -1, 0], scale=1))
                    ).stddev[0]
                    ** 2
                )
                scored.append((not faded, sharpness, -abs(time - timestamp), time, frame))
        if not scored:
            raise InputError("No requested frame could be decoded.")
        _, sharpness, _, selected_time, frame = max(scored)
        with open_image(str(frame)) as image:
            if box:
                pixel_box = tuple(
                    round(v if box_units == "pixels" else v * (image.width if i % 2 == 0 else image.height) / 1000)
                    for i, v in enumerate(box)
                )
                if pixel_box[2] > image.width or pixel_box[3] > image.height:
                    raise InputError("Pixel crop lies outside the displayed frame.")
                if pixel_box[2] <= pixel_box[0] or pixel_box[3] <= pixel_box[1]:
                    raise InputError("The requested crop is smaller than one pixel.")
                image = image.crop(pixel_box)
            image.convert("RGB").save(target)
            size = list(image.size)
    metadata = {
        "source_sha256": sha256(source),
        "output_sha256": sha256(target),
        "timestamp": selected_time,
        "box": box,
        "box_units": box_units,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    return {
        "status": "saved",
        "path": str(target),
        "metadata_path": str(metadata_path),
        "timestamp": selected_time,
        "requested_timestamp": timestamp,
        "box": box,
        "box_units": box_units,
        "size": size,
        "sharpness": sharpness,
        "source_sha256": sha256(source),
    }


def read_pdf_worker(arguments: dict) -> dict:
    """PDFium runs in its own process; text and image files remain portable evidence."""
    import pypdfium2 as pdfium

    source = local_file(arguments["file_path"])
    output = new_output(arguments["output_path"])
    if output.with_suffix(output.suffix + ".reading.json").exists():
        raise InputError("Document reading metadata already exists; choose a new output path.")
    with pdfium.PdfDocument(str(source)) as pdf:
        first = arguments.get("start_page", 1)
        last = min(arguments.get("end_page") or (first + 9 if arguments.get("render") else len(pdf)), len(pdf))
        if first > last:
            raise InputError("The page range is outside the PDF.")
        pages = []
        for number in range(first - 1, last):
            page = pdf[number]
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            textpage.close()
            record = {"page": number + 1, "text": text}
            if arguments.get("render"):
                frame = output.parent / f"{output.stem}-page-{number + 1}.png"
                if frame.exists():
                    raise InputError("A rendered page already exists; choose a new output name.")
                bitmap = page.render(scale=1.5)
                bitmap.to_pil().save(frame)
                bitmap.close()
                record["image"] = str(frame)
            page.close()
            pages.append(record)
        output.write_text("\n\n".join(f"Page {p['page']}\n{p['text']}" for p in pages), encoding="utf-8")
        result = {
            "status": "read",
            "total_pages": len(pdf),
            "pages": pages,
            "text_path": str(output),
            "source_sha256": sha256(source),
        }
        evidence = output.with_suffix(output.suffix + ".reading.json")
        evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        if sum(len(p["text"]) for p in pages) > 20000:
            result.update(pages=[{k: v for k, v in p.items() if k != "text"} for p in pages], text_in_preview=False)
        return {**result, "reading_record": str(evidence)}
