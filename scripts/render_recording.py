"""Render a verified Flights screencast to GIF/MP4 at 1x without replacing upstream media."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from examples.flights import verify  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    state = json.loads((source / "state.json").read_text())
    verified = verify(state["final_page"])
    assert verified["passed"] and not state["recording_errors"], "Only render independently verified runs"
    args.output.mkdir(parents=True, exist_ok=True)
    frames = [(0, source / "frames/000000.jpg")]
    frames += sorted((int(p.stem), p) for p in (source / "screencast").glob("*.jpg"))
    end = max(state["elapsed_ms"], frames[-1][0])
    rendered = source / "rendered"
    rendered.mkdir(exist_ok=True)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
    small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
    decision = state["decisions"][0]["model"]
    helper = state["text_calls"][0]["model"].split("/")[-1]
    fps = 12
    for i in range(round((end + 1000) * fps / 1000)):
        t = min(end, round(i * 1000 / fps))
        path = next(p for ts, p in reversed(frames) if ts <= t)
        with Image.open(path) as image:
            # Crop Google account controls. Retain the complete recorded task area.
            shot = image.convert("RGB").crop((0, 64, 1120, 780)).resize((960, 614))
        canvas = Image.new("RGB", (960, 710), "#f4f6f8")
        draw = ImageDraw.Draw(canvas)
        draw.text((18, 13), f"{decision} + {helper} · Cloudflare Workers AI", font=font, fill="#152b40")
        draw.text((18, 43), "Zürich → London · One way · 20 Nov 2026 · 1 adult · Economy", font=small, fill="#33495c")
        canvas.paste(shot, (0, 72))
        status = "Route, date, passenger and cabin verified" if t >= state["elapsed_ms"] else "Agent running"
        draw.text((12, 690), f"{t/1000:.1f}s · 1× original timing · {status}", font=small, fill="#152b40")
        canvas.save(rendered / f"{i:05d}.png")
    canvas.save(args.output / "flights-result.png")
    mp4 = args.output / "cloudflare-flights.mp4"
    gif = args.output / "cloudflare-flights.gif"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(rendered / "%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(mp4)],
                   check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf",
                    "split[a][b];[a]palettegen[p];[b][p]paletteuse", "-loop", "0", str(gif)], check=True)
    summary = {"goal": state["goal"], "decision_model": decision, "text_model": helper,
               "elapsed_ms": state["elapsed_ms"], "decisions": len(state["decisions"]),
               "actions": len(state["history"]), "text_calls": len(state["text_calls"]),
               "verification": verified, "recording_errors": state["recording_errors"],
               "video_speed": "1x", "final_hold_ms": 1000}
    (args.output / "verification.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
