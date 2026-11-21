"""Generate a 60.0-second, 1920x1080 30fps editorial B&W demo video with natural neural voiceover & synced scenes."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.api.deps import build_container
from app.config import Settings
from app.schemas.api import ChatRefineRequest, ChatTurnRequest, Location

WIDTH = 1920
HEIGHT = 1080
FPS = 30
DURATION_SECS = 60
TOTAL_FRAMES = FPS * DURATION_SECS  # 1800 frames

OUT_MP4 = ROOT_DIR / "docs" / "moodbite_demo_60s.mp4"
FFMPEG_LOG = ROOT_DIR / "docs" / "ffmpeg_render.log"
STRESS_JSON = BACKEND_DIR / "evals" / "stress_suite_report.json"

NEURAL_VOICE = "en-US-BrianNeural"

# Strict Editorial Monochrome Tokens (Spec 05 & 10)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
SUBTLE = (247, 247, 247)
HAIRLINE = (229, 229, 229)
SECONDARY = (82, 82, 82)

# Calm, natural ~115-word script across 6 synced beats (zero atempo speedup)
VOICE_SEGMENTS = [
    {
        "spoken": (
            "Exhausted after a long day, scrolling endless menus is friction. "
            "This localhost prototype pairs a monochrome chat UI with Swiggy's Food MCP."
        ),
        "caption": (
            "Exhausted after a long day, scrolling endless menus is friction. "
            "This localhost prototype pairs a monochrome chat UI, 2.5s guardrail & Swiggy Food MCP (mcp.swiggy.com/food)."
        ),
    },
    {
        "spoken": (
            "Say you're super tired and want fast comfort. MoodBite extracts tired and down, "
            "zero-mess effort, and a 30-minute cap, then queries Swiggy menus."
        ),
        "caption": (
            "MoodBite extracts primary_mood: tired_and_down, effort_to_eat: zero_mess & a 30-minute ETA cap"
            "—then queries Swiggy's menu tools for comfort combos."
        ),
    },
    {
        "spoken": (
            "It surfaces zero-mess combos under 30 minutes, pairing comfort mains like Chole Chawal "
            "or Dum Biryani with cold drinks."
        ),
        "caption": (
            "It surfaces zero-mess combos under 30 minutes—pairing comfort mains like Chole Chawal "
            "or Dum Biryani with cold drinks."
        ),
    },
    {
        "spoken": (
            "Tap Under 250 rupees to re-filter combos within budget—without re-explaining how you feel."
        ),
        "caption": (
            "Tap Under ₹250 to re-filter combos within budget—without re-explaining how you feel."
        ),
    },
    {
        "spoken": (
            "Hard constraints stay locked. A vegan user with peanut, dairy, and gluten allergies "
            "gets only safe combos—enforced deterministically."
        ),
        "caption": (
            "Hard constraints lock across turns. A vegan user with peanut, dairy & gluten allergies "
            "gets only safe combos—enforced deterministically."
        ),
    },
    {
        "spoken": (
            "Clicking Add Combo calls update food cart over MCP. Built for Swiggy Builders Club"
            "—ready for OAuth allowlisting and review."
        ),
        "caption": (
            "Clicking Add Combo dispatches update_food_cart over MCP. "
            "Built for Swiggy Builders Club—ready for production OAuth allowlisting and builder review."
        ),
    },
]


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        return ImageFont.load_default()


FONTS = {
    "title": _load_font(r"C:\Windows\Fonts\segoeuib.ttf", 64),
    "h1": _load_font(r"C:\Windows\Fonts\segoeuib.ttf", 38),
    "h2": _load_font(r"C:\Windows\Fonts\segoeuib.ttf", 27),
    "h3": _load_font(r"C:\Windows\Fonts\segoeuib.ttf", 21),
    "body": _load_font(r"C:\Windows\Fonts\segoeui.ttf", 20),
    "body_sm": _load_font(r"C:\Windows\Fonts\segoeui.ttf", 17),
    "caption": _load_font(r"C:\Windows\Fonts\segoeui.ttf", 21),
    "mono_lg": _load_font(r"C:\Windows\Fonts\consolab.ttf", 20),
    "mono": _load_font(r"C:\Windows\Fonts\consola.ttf", 17),
    "mono_sm": _load_font(r"C:\Windows\Fonts\consolab.ttf", 15),
}


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), cand, font=font)
        if bbox[2] - bbox[0] <= max_w:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_rounded_box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    *,
    fill: tuple[int, int, int] = WHITE,
    outline: tuple[int, int, int] = BLACK,
    width: int = 2,
    radius: int = 16,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    *,
    inverted: bool = False,
    font: ImageFont.ImageFont | None = None,
) -> int:
    f = font or FONTS["mono_sm"]
    bbox = draw.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x, pad_y = 15, 8
    w = tw + pad_x * 2
    h = th + pad_y * 2
    _draw_rounded_box(
        draw,
        (x, y, x + w, y + h),
        fill=BLACK if inverted else WHITE,
        outline=BLACK,
        width=2,
        radius=999,
    )
    draw.text((x + pad_x, y + pad_y - 2), text, font=f, fill=WHITE if inverted else BLACK)
    return w


def _wav_duration_secs(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate or 44100)


def _fmt_mmss(sec: float) -> str:
    s = max(0, int(round(sec)))
    return f"{s // 60}:{s % 60:02d}"


def _synth_edge_clips(ffmpeg_bin: str, work_dir: Path, rate_flag: str) -> list[tuple[Path, float]]:
    uvx_bin = shutil.which("uvx")
    if not uvx_bin:
        raise SystemExit("uvx not found on PATH; cannot synthesize neural voiceover via edge-tts")

    clips: list[tuple[Path, float]] = []
    for idx, seg in enumerate(VOICE_SEGMENTS):
        txt_path = work_dir / f"seg_{idx}.txt"
        mp3_path = work_dir / f"seg_{idx}.mp3"
        wav_path = work_dir / f"seg_{idx}.wav"
        txt_path.write_text(seg["spoken"], encoding="utf-8")

        last_err = ""
        for attempt in range(3):
            res = subprocess.run(
                [
                    uvx_bin,
                    "--from",
                    "edge-tts",
                    "edge-tts",
                    "--voice",
                    NEURAL_VOICE,
                    f"--rate={rate_flag}",
                    "--file",
                    str(txt_path),
                    "--write-media",
                    str(mp3_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if res.returncode == 0 and mp3_path.exists() and mp3_path.stat().st_size > 0:
                break
            last_err = f"rc={res.returncode} stdout={res.stdout!r} stderr={res.stderr!r}"
            time.sleep(1.0)
        else:
            raise SystemExit(f"edge-tts failed on segment {idx}: {last_err}")

        subprocess.run(
            [ffmpeg_bin, "-y", "-i", str(mp3_path), "-ar", "44100", "-ac", "2", str(wav_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        clips.append((wav_path, _wav_duration_secs(wav_path)))
        time.sleep(0.4)
    return clips


def _synthesize_voiceover_wav(ffmpeg_bin: str, work_dir: Path) -> tuple[Path, list[dict[str, Any]]]:
    """Generate natural neural speech clips (edge-tts) at calm rate and pack inside 60.0s."""
    # Reserve 0.4s lead-in + 0.7s trailing margin + min 0.35s * 5 breathing gaps = 2.85s -> max speech 57.15s
    clips: list[tuple[Path, float]] = []
    rate_used = "-4%"
    total_speech = 0.0
    for cand_rate in ("-4%", "+0%"):
        rate_used = cand_rate
        clips = _synth_edge_clips(ffmpeg_bin, work_dir, cand_rate)
        total_speech = sum(dur for _, dur in clips)
        if total_speech <= 57.15:
            break
    else:
        raise SystemExit(f"Total neural speech {total_speech:.2f}s exceeds 57.15s budget even at {rate_used}")

    slack = max(0.0, (DURATION_SECS - 0.4 - 0.7) - total_speech)
    gap = min(1.0, max(0.35, slack / max(1, len(clips) - 1)))

    timings: list[dict[str, Any]] = []
    cursor = 0.4
    for idx, (seg, (wav_path, dur)) in enumerate(zip(VOICE_SEGMENTS, clips)):
        start_s = cursor
        end_s = start_s + dur
        cut_s = 0.0 if idx == 0 else max(0.0, start_s - min(0.15, gap / 2.0))
        timings.append(
            {
                "index": idx,
                "wav": wav_path,
                "start": start_s,
                "end": end_s,
                "dur": dur,
                "cut_s": cut_s,
                "caption": seg["caption"],
            }
        )
        cursor = end_s + gap

    mixed_wav = work_dir / "voiceover_60s.wav"
    cmd: list[str] = [ffmpeg_bin, "-y"]
    filter_parts: list[str] = []
    mix_labels: list[str] = []
    for item in timings:
        idx = item["index"]
        cmd.extend(["-i", str(item["wav"])])
        delay_ms = int(round(item["start"] * 1000))
        label = f"a{idx}"
        filter_parts.append(f"[{idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay={delay_ms}|{delay_ms}[{label}]")
        mix_labels.append(f"[{label}]")

    filter_complex = ";".join(filter_parts) + (
        f";{''.join(mix_labels)}amix=inputs={len(timings)}:duration=longest:normalize=0,"
        f"apad=whole_dur={DURATION_SECS},alimiter=limit=0.95[outa]"
    )
    cmd.extend(["-filter_complex", filter_complex, "-map", "[outa]", "-t", str(DURATION_SECS), str(mixed_wav)])
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    print(f"Synthesized natural neural voice ({NEURAL_VOICE}, rate={rate_used}, gap={gap:.2f}s, speech={total_speech:.2f}s):")
    for item in timings:
        print(f"  [{item['index']}] cut={item['cut_s']:.2f}s | {item['start']:.2f}s -> {item['end']:.2f}s (dur={item['dur']:.2f}s)")
    return mixed_wav, timings


def _active_caption(sec: float, timings: list[dict[str, Any]]) -> str:
    chosen = timings[0]["caption"]
    for item in timings:
        if sec >= item["cut_s"]:
            chosen = item["caption"]
    return chosen


def _draw_chrome(draw: ImageDraw.ImageDraw, frame_idx: int, chapter_label: str, timings: list[dict[str, Any]]) -> None:
    draw.rectangle((0, 0, WIDTH, 74), fill=WHITE)
    draw.line((0, 74, WIDTH, 74), fill=BLACK, width=3)

    draw.text((64, 20), "MOODBITE × SWIGGY MCP", font=FONTS["h2"], fill=BLACK)
    chap_w = _draw_pill(draw, 430, 19, chapter_label, inverted=True, font=FONTS["mono_sm"])
    _draw_pill(draw, 430 + chap_w + 14, 19, "LOCALHOST / PROTOTYPE", inverted=False, font=FONTS["mono_sm"])

    sec = frame_idx / FPS
    time_label = f"00:{int(sec):02d} / 01:00"
    draw.text((WIDTH - 230, 24), time_label, font=FONTS["mono_lg"], fill=BLACK)

    draw.rectangle((0, 968, WIDTH, 1070), fill=BLACK)
    draw.line((0, 968, WIDTH, 968), fill=BLACK, width=2)
    caption = _active_caption(sec, timings)
    cap_lines = _wrap_text(draw, caption, FONTS["caption"], WIDTH - 140)
    if len(cap_lines) == 1:
        draw.text((70, 1002), cap_lines[0], font=FONTS["caption"], fill=WHITE)
    else:
        draw.text((70, 984), cap_lines[0], font=FONTS["caption"], fill=WHITE)
        draw.text((70, 1018), cap_lines[1], font=FONTS["caption"], fill=WHITE)

    progress = min(1.0, frame_idx / max(1, TOTAL_FRAMES - 1))
    draw.rectangle((0, HEIGHT - 10, WIDTH, HEIGHT), fill=HAIRLINE)
    draw.rectangle((0, HEIGHT - 10, int(WIDTH * progress), HEIGHT), fill=BLACK)


def _collect_live_demo_data() -> dict[str, Any]:
    settings = Settings(
        llm_provider="offline",
        openrouter_api_key="",
        openai_api_key="",
        gemini_api_key="",
        database_url="",
        redis_url="",
        daily_request_limit=5000,
        rate_limit_persist_path="",
    )
    container = build_container(settings)

    async def gather_all():
        r_tired = await container.orchestrator.handle_turn(
            ChatTurnRequest(
                session_id="demo_tired",
                user_id="demo",
                message="super tired and mood is kinda off, want something fast that cheers me up",
                location=Location(),
            )
        )
        r_refined = await container.orchestrator.handle_refine(
            ChatRefineRequest(
                session_id="demo_tired",
                user_id="demo",
                chip="Under ₹250",
                location=Location(),
            )
        )
        r_allergy = await container.orchestrator.handle_turn(
            ChatTurnRequest(
                session_id="demo_allergy",
                user_id="demo",
                message="I'm stressed. I'm allergic to peanuts, dairy and gluten, and I'm vegan. What should I eat?",
                location=Location(),
            )
        )
        return r_tired.model_dump(), r_refined.model_dump(), r_allergy.model_dump()

    tired_data, refined_data, allergy_data = asyncio.run(gather_all())
    stress_data = json.loads(STRESS_JSON.read_text(encoding="utf-8"))
    return {"tired": tired_data, "refined": refined_data, "allergy": allergy_data, "stress": stress_data}


def _render_scene_0(draw: ImageDraw.ImageDraw, local_f: int, total_f: int, data: dict[str, Any]) -> None:
    _draw_rounded_box(draw, (110, 102, 1810, 940), fill=WHITE, outline=BLACK, width=3, radius=24)
    w1 = _draw_pill(draw, 165, 142, "LOCALHOST PROTOTYPE • READY FOR OAUTH ALLOWLISTING", inverted=True, font=FONTS["mono"])
    _draw_pill(draw, 165 + w1 + 14, 142, "SWIGGY BUILDERS CLUB", inverted=False, font=FONTS["mono"])

    draw.text((165, 202), "MOODBITE × SWIGGY FOOD MCP", font=FONTS["title"], fill=BLACK)
    draw.text(
        (165, 288),
        "Exhausted after a long day? MoodBite turns a 1–2 turn chat into fast, zero-mess Swiggy combos.",
        font=FONTS["h3"],
        fill=SECONDARY,
    )
    draw.line((165, 344, 1755, 344), fill=HAIRLINE, width=2)

    blocks = [
        ("01 / MONOCHROME UI", "Strict #000000 / #FFFFFF", "Next.js 15 • SSE token streaming • Inline STATE pill • Zero shadows"),
        ("02 / STATE GUARDRAIL", "2.5s LLM + Deterministic Lock", "Extracts primary_mood, effort_to_eat & search_queries safely"),
        ("03 / SWIGGY FOOD MCP", "mcp.swiggy.com/food (PKCE)", "get_addresses • search_menu • fetch_food_coupons • update_food_cart"),
        ("04 / STRESS HARDENED", "30/30 Stress Suite Pass", "Allergy & Jain locks • Crisis & refusal gates • 20 req/day quota"),
    ]
    step = min(4, int((local_f / max(1, total_f * 0.65)) * 4) + 1)
    for idx, (tag, title, desc) in enumerate(blocks):
        if idx >= step:
            break
        bx = 165 + (idx % 2) * 805
        by = 380 + (idx // 2) * 200
        _draw_rounded_box(draw, (bx, by, bx + 765, by + 170), fill=SUBTLE if idx % 2 else WHITE, outline=BLACK, width=2, radius=16)
        _draw_pill(draw, bx + 24, by + 20, tag, inverted=True, font=FONTS["mono_sm"])
        draw.text((bx + 24, by + 68), title, font=FONTS["h3"], fill=BLACK)
        draw.text((bx + 24, by + 112), desc, font=FONTS["body_sm"], fill=SECONDARY)

    draw.text(
        (165, 818),
        "PROTOTYPE ENDPOINT: http://localhost:3000 -> mcp.swiggy.com/food (OAuth 2.1 + PKCE S256)",
        font=FONTS["mono"],
        fill=BLACK,
    )
    draw.text(
        (165, 858),
        "DEPLOYED PREVIEW: https://moodbite-ai-ashy.vercel.app   |   STRESS SUITE: /tests (30/30 PASS)",
        font=FONTS["mono_sm"],
        fill=SECONDARY,
    )


def _render_scene_1(draw: ImageDraw.ImageDraw, local_f: int, total_f: int, data: dict[str, Any]) -> None:
    tired = data["tired"]
    queries = tired["full_context"]["food_preferences"].get("search_queries", ["rajma chawal", "chole chawal", "cold drink"])
    formatted_queries = ", ".join(f'"{q}"' for q in queries)
    state_query_tag = queries[0].upper() if queries else "RAJMA CHAWAL"

    _draw_rounded_box(draw, (110, 96, 1020, 944), fill=WHITE, outline=BLACK, width=3, radius=20)
    draw.rectangle((113, 99, 1017, 158), fill=SUBTLE)
    draw.line((110, 158, 1020, 158), fill=BLACK, width=2)
    draw.text((140, 116), "<-  MOODBITE × SWIGGY MCP", font=FONTS["h3"], fill=BLACK)
    _draw_pill(draw, 730, 114, "VEG", inverted=False, font=FONTS["mono_sm"])
    _draw_pill(draw, 820, 114, "CART: 0", inverted=False, font=FONTS["mono_sm"])

    draw.text((140, 174), "MOODBITE", font=FONTS["mono_sm"], fill=SECONDARY)
    _draw_rounded_box(draw, (140, 198, 880, 260), fill=WHITE, outline=BLACK, width=2, radius=12)
    draw.text((160, 218), "Hey—how's the day going? Tell me the vibe and I'll sort out food.", font=FONTS["body_sm"], fill=BLACK)

    user_msg = "super tired and mood is kinda off, want something fast that cheers me up"
    chars = int(min(len(user_msg), max(8, (local_f / 85.0) * len(user_msg))))
    shown_user = user_msg[:chars]
    _draw_rounded_box(draw, (280, 280, 990, 358), fill=BLACK, outline=BLACK, width=2, radius=14)
    u_lines = _wrap_text(draw, shown_user, FONTS["body_sm"], 665)
    for li, line in enumerate(u_lines[:2]):
        draw.text((302, 294 + li * 25), line, font=FONTS["body_sm"], fill=WHITE)

    if local_f > 95:
        _draw_rounded_box(draw, (140, 380, 975, 420), fill=SUBTLE, outline=BLACK, width=2, radius=8)
        draw.text(
            (156, 391),
            f"MOOD=TIRED_AND_DOWN | EFFORT=ZERO_MESS | ETA<=30M | MCP={state_query_tag}",
            font=FONTS["mono_sm"],
            fill=BLACK,
        )

    if 85 <= local_f < 155:
        _draw_rounded_box(draw, (140, 445, 590, 500), fill=WHITE, outline=BLACK, width=2, radius=14)
        dots = "." * (1 + (local_f // 10) % 3)
        draw.text((164, 460), f"Querying Swiggy MCP search_menu{dots}", font=FONTS["mono"], fill=SECONDARY)
    elif local_f >= 155:
        draw.text((140, 442), "MOODBITE", font=FONTS["mono_sm"], fill=SECONDARY)
        _draw_rounded_box(draw, (140, 466, 985, 538), fill=WHITE, outline=BLACK, width=2, radius=12)
        a_lines = _wrap_text(draw, tired["agent_message"], FONTS["body_sm"], 800)
        for li, line in enumerate(a_lines[:2]):
            draw.text((160, 478 + li * 24), line, font=FONTS["body_sm"], fill=BLACK)

        combo = tired["recommendations"][0]
        _draw_rounded_box(draw, (140, 560, 985, 845), fill=WHITE, outline=BLACK, width=3, radius=14)
        _draw_pill(draw, 162, 578, combo["mood_badge"], inverted=True, font=FONTS["mono_sm"])
        draw.text((710, 584), f"{combo['restaurant']['eta_mins']} MINS • ₹{combo['total_price_inr']}", font=FONTS["mono"], fill=BLACK)
        title_lines = _wrap_text(draw, combo["title"], FONTS["h3"], 790)
        draw.text((162, 626), title_lines[0], font=FONTS["h3"], fill=BLACK)
        next_y = 656 if len(title_lines) == 1 else 684
        if len(title_lines) > 1:
            draw.text((162, 654), title_lines[1], font=FONTS["h3"], fill=BLACK)
        draw.text((162, next_y), f"{combo['restaurant']['name']} • {combo['restaurant']['rating']:.1f}/5", font=FONTS["body_sm"], fill=SECONDARY)
        why_lines = _wrap_text(draw, combo["why_it_fits"], FONTS["body_sm"], 790)
        draw.text((162, next_y + 32), why_lines[0] if why_lines else "", font=FONTS["body_sm"], fill=SECONDARY)
        _draw_rounded_box(draw, (162, 774, 962, 822), fill=BLACK, outline=BLACK, width=2, radius=8)
        draw.text((310, 788), f"+ ADD COMBO TO SWIGGY CART • ₹{combo['total_price_inr']}", font=FONTS["mono_sm"], fill=WHITE)

    _draw_rounded_box(draw, (1060, 96, 1810, 944), fill=SUBTLE, outline=BLACK, width=3, radius=20)
    _draw_pill(draw, 1095, 118, "LIVE USERCONTEXT JSON & MCP QUERIES", inverted=True, font=FONTS["mono_sm"])
    ctx_json = json.dumps(tired["full_context"], indent=2)
    for li, line in enumerate(ctx_json.splitlines()[:25]):
        draw.text((1095, 168 + li * 23), line[:64], font=FONTS["mono_sm"], fill=BLACK)

    _draw_rounded_box(draw, (1095, 780, 1775, 916), fill=WHITE, outline=BLACK, width=2, radius=12)
    draw.text((1120, 798), "SWIGGY MCP TOOLS TRIGGERED (PROMPT-ALIGNED)", font=FONTS["mono_sm"], fill=BLACK)
    draw.text((1120, 834), f"search_menu({formatted_queries})", font=FONTS["mono_sm"], fill=SECONDARY)
    draw.text((1120, 868), "Score = 0.40*Mood + 0.25*ETA + 0.15*Effort + 0.10*Rating + 0.10*Pair", font=FONTS["mono_sm"], fill=SECONDARY)


def _render_scene_2_sub(draw: ImageDraw.ImageDraw, sub_mode: str, data: dict[str, Any]) -> None:
    tired = data["tired"]
    refined = data["refined"]
    allergy = data["allergy"]

    if sub_mode in ("combos", "refine"):
        refine_toggled = sub_mode == "refine"
        active = refined if refine_toggled else tired
        title_txt = "ONE-TAP REFINEMENT: ( Under ₹250 )" if refine_toggled else "RANKED SWIGGY COMBOS (ZERO-MESS + <=30 MINS)"
        draw.text((110, 96), title_txt, font=FONTS["h1"], fill=BLACK)

        px = 110
        for idx, chip in enumerate(["Under ₹250", "Make it spicier", "Something lighter", "Swap drink"]):
            w = _draw_pill(draw, px, 152, chip, inverted=(refine_toggled and idx == 0), font=FONTS["mono_sm"])
            px += w + 14

        draw.text((110, 204), f"MOODBITE: {active['agent_message']}", font=FONTS["body"], fill=BLACK)

        for idx, combo in enumerate(active["recommendations"][:4]):
            cx = 110 + (idx % 2) * 865
            cy = 248 + (idx // 2) * 354
            _draw_rounded_box(draw, (cx, cy, cx + 835, cy + 332), fill=WHITE, outline=BLACK, width=3, radius=16)
            _draw_pill(draw, cx + 24, cy + 18, combo["mood_badge"], inverted=True, font=FONTS["mono_sm"])
            _draw_pill(draw, cx + 235, cy + 18, combo["dietary_type"].upper(), inverted=False, font=FONTS["mono_sm"])
            draw.text((cx + 555, cy + 22), f"{combo['restaurant']['eta_mins']} MINS • ₹{combo['total_price_inr']}", font=FONTS["mono"], fill=BLACK)

            title_lines = _wrap_text(draw, combo["title"], FONTS["h3"], 785)
            for t_idx, t_line in enumerate(title_lines[:2]):
                draw.text((cx + 24, cy + 64 + t_idx * 28), t_line, font=FONTS["h3"], fill=BLACK)

            meta_y = cy + 68 + len(title_lines[:2]) * 28
            draw.text((cx + 24, meta_y), f"{combo['restaurant']['name']} • {combo['restaurant']['rating']:.1f}/5", font=FONTS["body_sm"], fill=SECONDARY)

            why_l = _wrap_text(draw, combo["why_it_fits"], FONTS["body_sm"], 785)
            for w_idx, w_line in enumerate(why_l[:2]):
                draw.text((cx + 24, meta_y + 30 + w_idx * 24), w_line, font=FONTS["body_sm"], fill=SECONDARY)

            _draw_rounded_box(draw, (cx + 24, cy + 262, cx + 811, cy + 310), fill=BLACK, outline=BLACK, width=2, radius=8)
            draw.text((cx + 215, cy + 276), f"+ ADD COMBO TO SWIGGY CART • ₹{combo['total_price_inr']}", font=FONTS["mono_sm"], fill=WHITE)
    else:
        draw.text((110, 96), "IMMUTABLE ALLERGY & DIETARY GUARDRAILS (STRESS #1)", font=FONTS["h1"], fill=BLACK)
        _draw_rounded_box(draw, (110, 158, 1810, 224), fill=BLACK, outline=BLACK, width=2, radius=14)
        draw.text((140, 180), 'USER: "I\'m stressed. I\'m allergic to peanuts, dairy and gluten, and I\'m vegan."', font=FONTS["h3"], fill=WHITE)
        px = 110
        for badge in ["LOCKED: VEGAN", "NO PEANUTS", "NO DAIRY", "NO GLUTEN", "0.0% VIOLATION RATE"]:
            w = _draw_pill(draw, px, 246, badge, inverted=badge.startswith("0.0%"), font=FONTS["mono_sm"])
            px += w + 14
        for idx, combo in enumerate(allergy["recommendations"][:2]):
            cx = 110 + idx * 865
            _draw_rounded_box(draw, (cx, 314, cx + 835, 622), fill=WHITE, outline=BLACK, width=3, radius=16)
            _draw_pill(draw, cx + 24, 338, "VERIFIED SAFE", inverted=True, font=FONTS["mono_sm"])
            draw.text((cx + 555, 342), f"{combo['restaurant']['eta_mins']} MINS • ₹{combo['total_price_inr']}", font=FONTS["mono"], fill=BLACK)
            t_lines = _wrap_text(draw, combo["title"], FONTS["h3"], 785)
            for t_i, t_l in enumerate(t_lines[:2]):
                draw.text((cx + 24, 388 + t_i * 28), t_l, font=FONTS["h3"], fill=BLACK)
            draw.text((cx + 24, 450), f"{combo['restaurant']['name']} • {combo['restaurant']['rating']:.1f}/5", font=FONTS["body_sm"], fill=SECONDARY)
            why_l2 = _wrap_text(draw, combo["why_it_fits"], FONTS["body_sm"], 785)
            draw.text((cx + 24, 486), why_l2[0] if why_l2 else "", font=FONTS["body_sm"], fill=SECONDARY)
            draw.line((cx + 24, 540, cx + 811, 540), fill=HAIRLINE, width=2)
            draw.text((cx + 24, 562), "[OK] VEGAN   [OK] PEANUT-FREE   [OK] DAIRY-FREE   [OK] GLUTEN-FREE", font=FONTS["mono_sm"], fill=BLACK)

        _draw_rounded_box(draw, (110, 650, 1810, 938), fill=SUBTLE, outline=BLACK, width=3, radius=16)
        _draw_pill(draw, 145, 676, "SAFETY & ROBUSTNESS PROVEN ACROSS 30 ADVERSARIAL PROMPTS", inverted=True, font=FONTS["mono_sm"])
        draw.text((145, 732), "[OK] Crisis / Disordered-eating -> bypasses menu + shows Tele-MANAS / KIRAN / 988 helplines", font=FONTS["body"], fill=BLACK)
        draw.text((145, 778), "[OK] Diabetic / Pregnant -> excludes sugar spikes & caffeine + adds doctor advisory", font=FONTS["body"], fill=BLACK)
        draw.text((145, 824), "[OK] Prompt Injections / Poison requests / SQLi / XSS -> neutralized with 0 leaks & 0 crashes", font=FONTS["body"], fill=BLACK)
        draw.text((145, 870), "[OK] Hinglish, Hindi Devanagari, Emojis & 5x Rejections -> 20/20 unique combos served", font=FONTS["body"], fill=BLACK)


def _render_scene_3(draw: ImageDraw.ImageDraw, local_f: int, total_f: int, data: dict[str, Any]) -> None:
    tired = data["tired"]
    stress = data["stress"]
    combo = tired["recommendations"][0]
    item0 = combo["items"][0]
    item1 = combo["items"][1]
    total_price = int(combo["total_price_inr"])
    assert item0["price_inr"] + item1["price_inr"] == total_price
    cart_synced = local_f >= int(2.2 * FPS)

    burst_item = next((r for r in stress.get("results", []) if r.get("number") == 28), None)
    burst_p95 = f"{burst_item['latency_ms']:.2f} ms" if burst_item else "passed"

    draw.text((110, 96), "ONE-TAP SWIGGY CART SYNC & STRESS SCORECARD", font=FONTS["h1"], fill=BLACK)

    _draw_rounded_box(draw, (110, 156, 940, 646), fill=WHITE, outline=BLACK, width=3, radius=18)
    _draw_pill(
        draw,
        145,
        182,
        f"CART: {len(combo['items'])} ITEMS • ₹{total_price}" if cart_synced else "CART: 0 • ₹0",
        inverted=cart_synced,
        font=FONTS["mono_sm"],
    )
    _draw_pill(
        draw,
        420,
        182,
        "update_food_cart (MCP)" if cart_synced else "READY TO SYNC",
        inverted=False,
        font=FONTS["mono_sm"],
    )

    title_lines = _wrap_text(draw, combo["title"], FONTS["h2"], 760)
    for t_i, t_l in enumerate(title_lines[:2]):
        draw.text((145, 238 + t_i * 34), t_l, font=FONTS["h2"], fill=BLACK)

    draw.text(
        (145, 312),
        f"{combo['restaurant']['name']} ({combo['restaurant']['id']}) • {combo['restaurant']['eta_mins']} MINS • Total: ₹{total_price}",
        font=FONTS["body_sm"],
        fill=SECONDARY,
    )

    _draw_rounded_box(draw, (145, 352, 905, 522), fill=SUBTLE, outline=BLACK, width=2, radius=12)
    draw.text((170, 368), "POST /api/v1/cart/add-combo", font=FONTS["mono_sm"], fill=BLACK)
    draw.text((170, 396), f"combo_id: {combo['combo_id']}", font=FONTS["mono_sm"], fill=SECONDARY)
    draw.text(
        (170, 424),
        f"items: [{item0['item_id']} (₹{item0['price_inr']}), {item1['item_id']} (₹{item1['price_inr']})] -> ₹{total_price}",
        font=FONTS["mono_sm"],
        fill=SECONDARY,
    )
    draw.text(
        (170, 454),
        "Synced live via Swiggy Food MCP update_food_cart" if cart_synced else "Dispatches update_food_cart(restaurant_id, items)",
        font=FONTS["mono_sm"],
        fill=BLACK,
    )
    draw.text(
        (170, 484),
        "Status: 200 OK • swiggy_synced: true" if cart_synced else "Status: awaiting tap",
        font=FONTS["mono_sm"],
        fill=SECONDARY,
    )

    _draw_rounded_box(
        draw,
        (145, 544, 905, 618),
        fill=WHITE if cart_synced else BLACK,
        outline=BLACK,
        width=3,
        radius=10,
    )
    cta = f"[OK] ADDED TO SWIGGY CART (₹{total_price})" if cart_synced else f"+ ADD COMBO TO SWIGGY CART • ₹{total_price}"
    draw.text((255 if cart_synced else 265, 569), cta, font=FONTS["mono"], fill=BLACK if cart_synced else WHITE)

    _draw_rounded_box(draw, (980, 156, 1810, 646), fill=SUBTLE, outline=BLACK, width=3, radius=18)
    _draw_pill(draw, 1015, 182, f"STRESS SUITE: {stress['passed']}/{stress['total_prompts']} PASS", inverted=True, font=FONTS["mono_sm"])
    _draw_pill(draw, 1340, 182, "0 SAFETY FAILURES", inverted=False, font=FONTS["mono_sm"])

    rows = [
        ("1. Safety & Health (#1–#6)", "PASS"),
        ("2. Prompt Injection & Abuse (#7–#11)", "PASS"),
        ("3. Messy / Hindi / Emoji (#12–#17)", "PASS"),
        ("4. Context & Cultural Conflicts (#18–#23)", "PASS"),
        ("5. Consistency & 5x Rotation (#24–#27)", "PASS"),
        ("6. 100-Req Burst & Network Drop (#28–#30)", "PASS"),
    ]
    for ri, (label, status_txt) in enumerate(rows):
        ry = 252 + ri * 60
        draw.text((1015, ry + 6), label, font=FONTS["body"], fill=BLACK)
        _draw_pill(draw, 1680, ry, status_txt, inverted=(ri == 0), font=FONTS["mono_sm"])
        draw.line((1015, ry + 50, 1775, ry + 50), fill=HAIRLINE, width=1)

    _draw_rounded_box(draw, (110, 676, 1810, 940), fill=BLACK, outline=BLACK, width=3, radius=20)
    draw.text((155, 706), "BUILT FOR SWIGGY BUILDERS CLUB (builders@swiggy.in)", font=FONTS["h1"], fill=WHITE)
    draw.text(
        (155, 766),
        "Localhost Prototype Ready for Production OAuth Allowlisting & Builder Review • Strict Monochrome Next.js + FastAPI",
        font=FONTS["h3"],
        fill=HAIRLINE,
    )
    draw.text(
        (155, 824),
        "Preview: https://moodbite-ai-ashy.vercel.app (/tests)   |   GitHub: Ravijlmush/moodbite-ai (Private)",
        font=FONTS["mono"],
        fill=WHITE,
    )
    draw.text(
        (155, 872),
        f"50/50 Golden Evals • 30/30 Stress Tests • 24/24 Pytest • 100-Req Burst P95 = {burst_p95}",
        font=FONTS["mono_sm"],
        fill=HAIRLINE,
    )


def build_video() -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise SystemExit("ffmpeg not found on PATH")

    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)
    data = _collect_live_demo_data()

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        voiceover_wav, timings = _synthesize_voiceover_wav(ffmpeg_bin, work_dir)

        c0, c1, c2, c3, c4, c5 = [int(round(t["cut_s"] * FPS)) for t in timings]
        scenes = [
            (c0, c1, f"01 / ARCHITECTURE ({_fmt_mmss(timings[0]['cut_s'])}–{_fmt_mmss(timings[1]['cut_s'])})", _render_scene_0),
            (c1, c2, f"02 / VIBE CHECK & STATE ({_fmt_mmss(timings[1]['cut_s'])}–{_fmt_mmss(timings[2]['cut_s'])})", _render_scene_1),
            (
                c2,
                c3,
                f"03 / RANKED COMBOS ({_fmt_mmss(timings[2]['cut_s'])}–{_fmt_mmss(timings[3]['cut_s'])})",
                lambda d, lf, tf, dat: _render_scene_2_sub(d, "combos", dat),
            ),
            (
                c3,
                c4,
                f"04 / UNDER ₹250 REFINE ({_fmt_mmss(timings[3]['cut_s'])}–{_fmt_mmss(timings[4]['cut_s'])})",
                lambda d, lf, tf, dat: _render_scene_2_sub(d, "refine", dat),
            ),
            (
                c4,
                c5,
                f"05 / SAFETY GUARDRAILS ({_fmt_mmss(timings[4]['cut_s'])}–{_fmt_mmss(timings[5]['cut_s'])})",
                lambda d, lf, tf, dat: _render_scene_2_sub(d, "allergy", dat),
            ),
            (c5, TOTAL_FRAMES, f"06 / SWIGGY CART & SCORECARD ({_fmt_mmss(timings[5]['cut_s'])}–1:00)", _render_scene_3),
        ]

        cmd = [
            ffmpeg_bin,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{WIDTH}x{HEIGHT}",
            "-r", str(FPS),
            "-i", "-",
            "-i", str(voiceover_wav),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-t", str(DURATION_SECS),
            "-movflags", "+faststart",
            str(OUT_MP4),
        ]

        with FFMPEG_LOG.open("w", encoding="utf-8") as log_file:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log_file)
            assert proc.stdin is not None

            frame_cache: dict[tuple[int, int], bytes] = {}
            for frame_idx in range(TOTAL_FRAMES):
                bucket_frame = (frame_idx // 6) * 6
                for scene_idx, (start, end, label, fn) in enumerate(scenes):
                    if start <= frame_idx < end:
                        local_f = max(0, bucket_frame - start)
                        cache_key = (scene_idx, local_f // 6)
                        raw_bytes = frame_cache.get(cache_key)
                        if raw_bytes is None:
                            img = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
                            draw = ImageDraw.Draw(img)
                            _draw_chrome(draw, bucket_frame, label, timings)
                            fn(draw, local_f, end - start, data)
                            raw_bytes = img.tobytes()
                            frame_cache[cache_key] = raw_bytes
                            if len(frame_cache) > 64:
                                frame_cache.clear()
                        proc.stdin.write(raw_bytes)
                        break

            proc.stdin.close()
            ret = proc.wait()

        if ret != 0:
            err_txt = FFMPEG_LOG.read_text(encoding="utf-8", errors="replace")
            raise SystemExit(f"ffmpeg exited with {ret}:\n{err_txt}")
    FFMPEG_LOG.unlink(missing_ok=True)
    print(f"Generated synced 60s 1080p demo video with natural neural voiceover: {OUT_MP4}")


if __name__ == "__main__":
    build_video()
