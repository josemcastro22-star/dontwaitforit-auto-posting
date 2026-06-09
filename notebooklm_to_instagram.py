import os, sys, json, time, requests, tempfile
from pathlib import Path
from PIL import Image
from datetime import datetime

NOTEBOOK_ID      = os.environ["NOTEBOOKLM_ID"]
IG_ACCESS_TOKEN  = os.environ["IG_ACCESS_TOKEN"]
IG_USER_ID       = os.environ["IG_USER_ID"]

DAILY_PROMPTS = {
    0: "Generate a portrait infographic about spinal cord injury motivation and mindset for Don't Wait For It nonprofit. Bold headline, 3-4 recovery facts, CTA to dontwaitforit.org",
    1: "Generate a portrait infographic about the latest SCI research and breakthroughs for Don't Wait For It nonprofit. Bold headline, 3-4 research facts, CTA to dontwaitforit.org",
    2: "Generate a portrait infographic about adaptive fitness and wellness for spinal cord injury for Don't Wait For It nonprofit. Bold headline, 3-4 tips, CTA to dontwaitforit.org",
    3: "Generate a portrait infographic about adaptive equipment and accessibility tips for SCI for Don't Wait For It nonprofit. Bold headline, 3-4 tips, CTA to dontwaitforit.org",
    4: "Generate a portrait infographic about SCI community stories and awareness for Don't Wait For It nonprofit. Bold headline, 3-4 facts, CTA to dontwaitforit.org",
}

CAPTIONS = {
    0: "Motivation Monday 💪 Don't wait for your recovery — we've got your back.\n\nApply for therapy assistance at dontwaitforit.org\n\n#SCI #SpinalCordInjury #DontWaitForIt #Motivation #Recovery",
    1: "Research Tuesday 🔬 Science is moving fast — stay informed.\n\nApply for therapy assistance at dontwaitforit.org\n\n#SCIResearch #SpinalCordInjury #DontWaitForIt #SCIAwareness",
    2: "Wellness Wednesday 🌿 Stay active, stay strong.\n\nApply for therapy assistance at dontwaitforit.org\n\n#AdaptiveFitness #SCI #DontWaitForIt #Wellness #AdaptiveSports",
    3: "Tips Thursday 💡 Small changes, big impact.\n\nApply for therapy assistance at dontwaitforit.org\n\n#AdaptiveEquipment #Accessibility #SCI #DontWaitForIt",
    4: "Feature Friday ⭐ Real people, real recovery.\n\nApply for therapy assistance at dontwaitforit.org\n\n#SCICommunity #DontWaitForIt #Nonprofit #SpinalCordInjury",
}

def load_cookies():
    cookies_json = os.environ["NOTEBOOKLM_COOKIES"]
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    tmp.write(cookies_json)
    tmp.close()
    return tmp.name

def generate_infographic(cookies_path, output_path):
    from notebooklm import Client as NotebookLM
    weekday = datetime.utcnow().weekday()
    prompt = DAILY_PROMPTS.get(weekday, DAILY_PROMPTS[0])
    print(f"Day: {weekday}, Prompt: {prompt[:60]}...")
    nlm = NotebookLM(cookies=cookies_path)
    notebook = nlm.get_notebook(NOTEBOOK_ID)
    infographic = notebook.generate(kind="infographic", prompt=prompt, orientation="portrait", wait=True, timeout=180)
    infographic.download(output_path)
    return output_path

def resize_for_instagram(input_path, output_path):
    img = Image.open(input_path).convert("RGB")
    img.thumbnail((1080, 1350), Image.LANCZOS)
    canvas = Image.new("RGB", (1080, 1350), (255, 255, 255))
    canvas.paste(img, ((1080 - img.width) // 2, (1350 - img.height) // 2))
    canvas.save(output_path, "JPEG", quality=95)
    return output_path

def upload_image(image_path):
    imgbb_key = os.environ.get("IMGBB_API_KEY")
    if imgbb_key:
        with open(image_path, "rb") as f:
            r = requests.post("https://api.imgbb.com/1/upload", params={"key": imgbb_key}, files={"image": f}, timeout=60)
        r.raise_for_status()
        return r.json()["data"]["url"]
    raise RuntimeError("Set IMGBB_API_KEY secret")

def post_to_instagram(image_url, caption):
    base = f"https://graph.facebook.com/v19.0/{IG_USER_ID}"
    r = requests.post(f"{base}/media", params={"image_url": image_url, "caption": caption, "access_token": IG_ACCESS_TOKEN}, timeout=30)
    r.raise_for_status()
    container_id = r.json()["id"]
    time.sleep(5)
    r = requests.post(f"{base}/media_publish", params={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN}, timeout=30)
    r.raise_for_status()
    print(f"Posted! ID: {r.json()['id']}")

def main():
    weekday = datetime.utcnow().weekday()
    with tempfile.TemporaryDirectory() as tmp:
        cookies_path = load_cookies()
        raw = f"{tmp}/raw.png"
        final = f"{tmp}/final.jpg"
        generate_infographic(cookies_path, raw)
        resize_for_instagram(raw, final)
        url = upload_image(final)
        caption = CAPTIONS.get(weekday, CAPTIONS[0])
        post_to_instagram(url, caption)
    print("Done!")

if __name__ == "__main__":
    main()
