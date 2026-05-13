import os
import sys
import json
import time
import subprocess
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

    prompt = f"""
You are generating ONE Instagram post for a nonprofit Instagram account focused on SCI/paralysis recovery.

Topic alignment:
- {TOPIC_FOCUS}

Style:
- {STYLE_GUIDELINES}

Hard requirements:
- Choose ONE timely, reputable topic.
- Provide:
  1) headline (max 6 words)
  2) big_stat (a single short stat/claim, max ~8 words, must be sourceable)
  3) bullets (exactly 3 bullets, each <= 12 words)
  4) source_line (very short, for the bottom of the image, e.g. "Source: Nature (2024)")
  5) caption (<= 1500 chars, include 3–8 hashtags, include 1–3 source links)
- Avoid claiming cures. Avoid diagnosis/treatment instructions.
- Make it visually punchy and scroll-stopping.

Return ONLY valid JSON with keys:
headline, big_stat, bullets, source_line, caption
"""

    body = {
        "model": "claude-3-5-sonnet-latest",
        "max_tokens": 800,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": prompt}],
    }

    r = requests.post(url, headers=headers, data=json.dumps(body), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Anthropic API error {r.status_code}: {r.text}")

    data = r.json()
    text = "".join(
        [p.get("text", "") for p in data.get("content", []) if p.get("type") == "text"]
    ).strip()

    try:
        return json.loads(text)
    except Exception:
        raise RuntimeError(f"Claude did not return valid JSON. Got:\n{text}")

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

def render_infographic(payload: dict, out_path: str):
    W, H = 1080, 1350
    bg = (10, 12, 18)          # near-black
    accent = (78, 255, 184)    # mint
    white = (245, 245, 245)
    muted = (170, 175, 185)

    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)

    headline_font = load_font(86)
    stat_font = load_font(120)
    bullet_font = load_font(48)
    source_font = load_font(30)

    # Accent bar
    d.rectangle([0, 0, W, 22], fill=accent)

    x_pad = 70
    y = 70

    # Headline
    head_lines = wrap_text(d, payload["headline"].upper(), headline_font, W - 2 * x_pad)
    for line in head_lines[:2]:
        d.text((x_pad, y), line, font=headline_font, fill=white)
        y += headline_font.size + 6

    y += 30

    # Big stat (center each line)
    stat = payload["big_stat"].upper()
    stat_lines = wrap_text(d, stat, stat_font, W - 2 * x_pad)
    for line in stat_lines[:3]:
        line_w = d.textlength(line, font=stat_font)
        d.text(((W - line_w) / 2, y), line, font=stat_font, fill=accent)
        y += stat_font.size + 4

    y += 35

    # Bullets
    for b in payload["bullets"]:
        b_lines = wrap_text(d, "• " + b, bullet_font, W - 2 * x_pad)
        for line in b_lines:
            d.text((x_pad, y), line, font=bullet_font, fill=white)
            y += bullet_font.size + 10
        y += 8

    # Bottom ribbon with source
    ribbon_h = 90
    d.rectangle([0, H - ribbon_h, W, H], fill=(18, 22, 32))
    d.text((x_pad, H - ribbon_h + 25), payload["source_line"], font=source_font, fill=muted)

    img.save(out_path, format="PNG")

def ensure_docs():
    os.makedirs("docs", exist_ok=True)

def write_outputs(payload: dict):
    ensure_docs()
    img_path = "docs/latest.png"
    txt_path = "docs/latest.txt"

    render_infographic(payload, img_path)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(payload["caption"].strip() + "\n")

def git_commit_push():
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)

    subprocess.run(["git", "add", "docs/latest.png", "docs/latest.txt"], check=True)

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
    r = requests.post(url, data=data, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Publish failed {r.status_code}: {r.text}")
    return r.json()["id"]

def main():
    ig_user_id = require_env("IG_USER_ID")
    ig_access_token = require_env("IG_ACCESS_TOKEN")
    anthropic_key = require_env("ANTHROPIC_API_KEY").strip()
    print("Anthropic key length:", len(anthropic_key))
    print("Anthropic key prefix:", anthropic_key[:7])  # should be 'sk-ant-'
    pages_base = require_env("PAGES_BASE_URL").rstrip("/")

    payload = anthropic_generate(anthropic_key)

    # Validate shape
    for k in ["headline", "big_stat", "bullets", "source_line", "caption"]:
        if k not in payload:
            raise RuntimeError(f"Missing key from Claude JSON: {k}")
    if not isinstance(payload["bullets"], list) or len(payload["bullets"]) != 3:
        raise RuntimeError("Claude JSON 'bullets' must be a list of exactly 3 items.")

    write_outputs(payload)
    pushed = git_commit_push()

    image_url = f"{pages_base}/latest.png"

    # If we pushed a new image, give Pages a moment to serve it
    if pushed:
        time.sleep(25)

    creation_id = ig_create_container(ig_user_id, ig_access_token, image_url, payload["caption"])
    media_id = ig_publish(ig_user_id, ig_access_token, creation_id)

    print("✅ Posted to Instagram. media_id =", media_id)
    print("Image URL used:", image_url)

if __name__ == "__main__":
    main()
