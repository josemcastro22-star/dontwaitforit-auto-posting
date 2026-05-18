import os
import sys
import json
import time
import subprocess
import hashlib
import random
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

import requests
from PIL import Image, ImageDraw, ImageFont

GRAPH_VERSION = "v25.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

TOPIC_FOCUS = (
    "Spinal cord injury awareness, paralysis recovery research, rehab technology, "
    "neuroprosthetics, exoskeletons, brain–spine interface, and evidence-based SCI stats."
)

STYLE_GUIDELINES = (
    "Nonprofit tone: hopeful, evidence-based, not hype. Avoid medical claims. "
    "Use plain language. Avoid giving medical advice. Include a short source line in the image "
    "and 1–3 source links in the caption."
)

def require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"Missing env var: {name}", file=sys.stderr)
        sys.exit(1)
    return v

def weekday_theme():
    now = datetime.now(ZoneInfo("America/New_York"))
    wd = now.weekday()  # Mon=0 Tue=1 Wed=2 Thu=3 Fri=4 Sat=5 Sun=6

    if wd == 0:
        return "MINDSET", (
            "Monday theme: Mindset & mental health for people impacted by spinal cord injuries/paralysis. "
            "Supportive, hopeful, practical encouragement. Avoid medical/therapy directives. "
            "Include a gentle resource line when appropriate."
        )

    if wd == 1:
        return "DISCOVERY", (
            "Tuesday theme: NEW research/discovery for SCI/paralysis recovery. "
            "Prefer peer‑reviewed research, clinical trials, reputable institutions. "
            "Explain what’s new + why it matters + include source links."
        )

    if wd == 2:
        return "ADAPTIVE_EQUIPMENT", (
            "Wednesday theme: Adaptive equipment / assistive tech for SCI—sports gear, wheelchair accessories, "
            "daily-living tools, mobility add-ons. Prefer newly released/announced items. Include source links."
        )

    if wd == 3:
        return "SCI_STATS", (
            "Thursday theme: Spinal cord injury stats & awareness. Use one strong stat and cite reputable sources "
            "(NSCISC, Reeve Foundation, NIH, CDC, etc.)."
        )

    return "GENERAL_SCI", "Default theme."

def anthropic_generate(api_key: str) -> dict:
    """
    Uses Anthropic Messages API. Returns structured JSON for the post.
    """
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key.strip(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    theme_name, theme_instructions = weekday_theme()

    prompt = f"""
You are generating ONE Instagram post for a nonprofit Instagram account focused on spinal cord injuries (SCI) and paralysis recovery.

THEME FOR TODAY: {theme_name}
{theme_instructions}

Topic alignment:
- {TOPIC_FOCUS}

Brand style:
- Tech modern / cyber vibe: clean, sharp, minimal words, high signal.
- Confident and evidence-based. No hype.
- No medical advice. No “cure” claims.

HARD REQUIREMENTS (follow strictly):
- Choose ONE timely, reputable topic aligned with THEME FOR TODAY.
- No clichés, no filler. Avoid: incredible, amazing, miracle, game-changer.
- Use numbers when possible. Every factual claim must be supported by sources in the caption.

TEXT FOR THE IMAGE (layout-safe, short):
1) headline:
   - MAX 5 words
   - specific (not generic “BREAKTHROUGH”)
2) big_stat:
   - MAX 10 words
   - punchy + concrete
3) bullets:
   - EXACTLY 2 bullets
   - each bullet MAX 9 words
   - no repeating the big_stat

CAPTION (where detail + sources go):
- 120–900 characters
- Structure:
  - 1 hook sentence
  - 2–4 short lines of context (plain language)
  - "Sources:" + 1–3 links
  - 3–8 SCI-specific hashtags

OUTPUT FORMAT:
Return ONLY raw JSON (no markdown fences/backticks, no commentary).
Keys (exactly these):
headline, big_stat, bullets, caption
""".strip()

    body = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 800,
        "temperature": 0.6,
        "messages": [{"role": "user", "content": prompt}],
    }

    r = requests.post(url, headers=headers, data=json.dumps(body), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Anthropic API error {r.status_code}: {r.text}")

    data = r.json()
    text = "".join(
        [p.get("text", "") for p in data.get("content", []) if p.get("type") == "text"]
    ).strip()

    # Strip ```json ... ``` if the model wraps it
    clean = text
    if "```" in clean:
        parts = clean.split("```")
        if len(parts) >= 2:
            clean = parts[1].lstrip()
            if clean.lower().startswith("json"):
                clean = clean[4:].lstrip()
    clean = clean.strip()

    try:
        payload = json.loads(clean)
    except Exception:
        raise RuntimeError(f"Claude did not return valid JSON. Got:\n{text}")

    # Hard validation (prevents ugly layouts)
    if not isinstance(payload.get("bullets"), list) or len(payload["bullets"]) != 2:
        raise RuntimeError("Claude JSON 'bullets' must be a list of exactly 2 items.")

    return payload
        
def load_font(size: int):
    # Ubuntu runner typically has DejaVu fonts.
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()

def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    cur = []
    for w in words:
        test = " ".join(cur + [w])
        if draw.textlength(test, font=font) <= max_width:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


HANDLE_TEXT = "@Dontwaitforit_Foundation"

def pick_hero_svg(theme_name: str) -> str | None:
    hero_dir = Path("assets/hero")
    if not hero_dir.exists():
        return None

    files = [p for p in hero_dir.iterdir() if p.suffix.lower() == ".svg"]
    if not files:
        return None

    name = theme_name.upper()

    buckets = {
        "MINDSET": ["meditat", "mindful", "mind", "yoga", "attitude", "positive", "community", "support"],
        "DISCOVERY": ["research", "science", "ai", "dev", "doctor", "articles", "productivity", "lab"],
        "ADAPTIVE_EQUIPMENT": ["devices", "online", "chat", "verify", "watching", "growing", "text"],
        "SCI_STATS": ["data", "stats", "statistics", "analytics", "insights", "result", "visual", "investment"],
    }

    keys = buckets.get(name, [])
    if keys:
        candidates = [p for p in files if any(k in p.name.lower() for k in keys)]
        if candidates:
            return str(random.choice(candidates))

    return str(random.choice(files))

def svg_to_png(svg_path: str, png_path: str, width: int = 900) -> None:
    subprocess.run(
        ["rsvg-convert", "-w", str(width), "-o", png_path, svg_path],
        check=True
    )

def render_infographic(payload: dict, out_path: str, theme_name: str):
    W, H = 1080, 1350

    NAVY_1 = (8, 18, 40)
    NAVY_2 = (16, 32, 66)
    ORANGE = (255, 122, 26)
    INK    = (10, 12, 18)
    MUTED  = (85, 95, 110)

    # background gradient
    bg = Image.new("RGB", (W, H), NAVY_1)
    px = bg.load()
    for y in range(H):
        t = y / (H - 1)
        r = int(NAVY_1[0] * (1 - t) + NAVY_2[0] * t)
        g = int(NAVY_1[1] * (1 - t) + NAVY_2[1] * t)
        b = int(NAVY_1[2] * (1 - t) + NAVY_2[2] * t)
        for x in range(W):
            px[x, y] = (r, g, b)

    img = bg.convert("RGBA")
    d = ImageDraw.Draw(img)

    # HERO (left)
    hero_svg = pick_hero_svg(theme_name)
    if hero_svg:
        os.makedirs("docs", exist_ok=True)
        tmp_png = "docs/_hero_tmp.png"
        svg_to_png(hero_svg, tmp_png, width=860)
        hero = Image.open(tmp_png).convert("RGBA")

        # place on left
        img.alpha_composite(hero, (40, 220))

    # CARD (right)
    card_x0, card_y0 = 560, 140
    card_x1, card_y1 = 1030, 1190

    d.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=44, fill=(255, 255, 255, 245))
    d.rounded_rectangle([card_x0, card_y0, card_x1, card_y0 + 16], radius=12, fill=(ORANGE[0], ORANGE[1], ORANGE[2], 255))

    headline_font = load_font(54)
    stat_font = load_font(64)
    bullet_font = load_font(34)
    source_font = load_font(26)
    handle_font = load_font(26)

    x_pad = card_x0 + 34
    y = card_y0 + 42
    max_w = (card_x1 - card_x0) - 68

    # headline
    head_lines = wrap_text(d, payload["headline"].upper(), headline_font, max_w)
    for line in head_lines[:2]:
        d.text((x_pad, y), line, font=headline_font, fill=INK)
        y += headline_font.size + 4

    y += 10

    # big stat
    stat_lines = wrap_text(d, payload["big_stat"], stat_font, max_w)
    for line in stat_lines[:3]:
        d.text((x_pad, y), line, font=stat_font, fill=ORANGE)
        y += stat_font.size + 2

    y += 10

    # bullets (2 only = cleaner)
    for b in payload["bullets"][:2]:
        b_lines = wrap_text(d, "• " + b, bullet_font, max_w)
        for line in b_lines:
            d.text((x_pad, y), line, font=bullet_font, fill=INK)
            y += bullet_font.size + 8
        y += 4

    # Embedded handle
    d.text((x_pad, card_y1 - 45), HANDLE_TEXT, font=handle_font, fill=ORANGE)

    # bottom accent bar
    d.rectangle([0, H - 8, W, H], fill=(ORANGE[0], ORANGE[1], ORANGE[2], 255))

    img.convert("RGB").save(out_path, format="PNG")
def ensure_docs():
    os.makedirs("docs", exist_ok=True)

def write_outputs(payload: dict, theme_name: str) -> str:
    ensure_docs()

    stamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d_%H%M")
    img_filename = f"post_{stamp}.png"

    img_path = f"docs/{img_filename}"
    txt_path = "docs/latest.txt"

    render_infographic(payload, img_path, theme_name)

    # optional: keep latest.png updated for preview
    render_infographic(payload, "docs/latest.png", theme_name)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(payload["caption"].strip() + "\n")

    return img_filename

def git_commit_push(img_filename: str):
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)

    subprocess.run(
    ["git", "add", f"docs/{img_filename}", "docs/latest.png", "docs/latest.txt"],
    check=True
    )
    
    # If nothing staged, do nothing
    r = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if r.returncode == 0:
        print("No changes to commit (outputs identical).")
        return False

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subprocess.run(["git", "commit", "-m", f"Update latest post assets ({stamp})"], check=True)

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Missing GITHUB_TOKEN (pass it from the workflow env).")

    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("Missing GITHUB_REPOSITORY environment variable.")

    remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
    subprocess.run(["git", "remote", "set-url", "origin", remote_url], check=True)
    subprocess.run(["git", "push", "origin", "HEAD:main"], check=True)
    return True

def ig_create_container(ig_user_id: str, access_token: str, image_url: str, caption: str) -> str:
    url = f"{GRAPH_BASE}/{ig_user_id}/media"
    data = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }
    r = requests.post(url, data=data, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Create container failed {r.status_code}: {r.text}")
    return r.json()["id"]

def ig_publish(ig_user_id: str, access_token: str, creation_id: str) -> str:
    url = f"{GRAPH_BASE}/{ig_user_id}/media_publish"
    data = {"creation_id": creation_id, "access_token": access_token}

    # Retry because IG sometimes needs time to finish processing the container
    for attempt in range(1, 9):  # ~8 tries
        r = requests.post(url, data=data, timeout=60)
        if r.status_code == 200:
            return r.json()["id"]

        try:
            err = r.json().get("error", {})
        except Exception:
            err = {}

        sub = err.get("error_subcode")
        msg = err.get("message", "")

        # "Media not ready" -> wait and retry
        if r.status_code == 400 and sub == 2207027:
            wait = 5 * attempt  # 5s, 10s, 15s...
            print(f"Publish not ready yet (attempt {attempt}). Waiting {wait}s...")
            time.sleep(wait)
            continue

        raise RuntimeError(f"Publish failed {r.status_code}: {r.text}")

    raise RuntimeError("Publish failed: media never became ready after retries.")

def wait_for_image(url: str, timeout_sec: int = 180) -> None:
    start = time.time()
    last_status = None
    while time.time() - start < timeout_sec:
        try:
            r = requests.get(url, timeout=20)
            last_status = r.status_code
            ctype = r.headers.get("Content-Type", "")
            if r.status_code == 200 and ctype.startswith("image/"):
                return
        except Exception:
            pass
        time.sleep(8)
    raise RuntimeError(f"Image not reachable as image within {timeout_sec}s. Last status={last_status}. URL={url}")
    
def main():
    ig_user_id = require_env("IG_USER_ID")
    ig_access_token = require_env("IG_ACCESS_TOKEN")
    anthropic_key = require_env("ANTHROPIC_API_KEY").strip()
    pages_base = require_env("PAGES_BASE_URL").rstrip("/")

    theme_name, _ = weekday_theme()
    payload = anthropic_generate(anthropic_key)

    # Validate shape
    for k in ["headline", "big_stat", "bullets", "caption"]:
        if k not in payload:
            raise RuntimeError(f"Missing key from Claude JSON: {k}")
    if not isinstance(payload["bullets"], list) or len(payload["bullets"]) != 3:
        raise RuntimeError("Claude JSON 'bullets' must be a list of exactly 3 items.")

    img_filename = write_outputs(payload, theme_name)
    pushed = git_commit_push(img_filename)

    image_url = f"{pages_base}/{img_filename}"
    wait_for_image(image_url, timeout_sec=240)

    # If we pushed a new image, give Pages a moment to serve it
    if pushed:
        time.sleep(25)

    creation_id = ig_create_container(ig_user_id, ig_access_token, image_url, payload["caption"])
    media_id = ig_publish(ig_user_id, ig_access_token, creation_id)

    print("✅ Posted to Instagram. media_id =", media_id)
    print("Image URL used:", image_url)

if __name__ == "__main__":
    main()
