import os, asyncio, json, time, requests, tempfile
from datetime import datetime
from pathlib import Path
from PIL import Image

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
    0: "Motivation Monday 💪 Don't wait for your recovery — we've got your back.\n\nApply at dontwaitforit.org\n\n#SCI #SpinalCordInjury #DontWaitForIt #Motivation #Recovery",
    1: "Research Tuesday 🔬 Science is moving fast — stay informed.\n\nApply at dontwaitforit.org\n\n#SCIResearch #SpinalCordInjury #DontWaitForIt #SCIAwareness",
    2: "Wellness Wednesday 🌿 Stay active, stay strong.\n\nApply at dontwaitforit.org\n\n#AdaptiveFitness #SCI #DontWaitForIt #Wellness",
    3: "Tips Thursday 💡 Small changes, big impact.\n\nApply at dontwaitforit.org\n\n#AdaptiveEquipment #Accessibility #SCI #DontWaitForIt",
    4: "Feature Friday ⭐ Real people, real recovery.\n\nApply at dontwaitforit.org\n\n#SCICommunity #DontWaitForIt #Nonprofit #SpinalCordInjury",
}

async def generate_infographic(storage_path, output_path):
    from notebooklm import NotebookLMClient
    from notebooklm.auth import AuthTokens
    weekday = datetime.utcnow().weekday()
    prompt = DAILY_PROMPTS.get(weekday, DAILY_PROMPTS[0])
    print(f"Day: {weekday}, Prompt: {prompt[:60]}...")
    auth = await AuthTokens.from_storage(Path(storage_path))
    async with NotebookLMClient(auth) as client:
        notebook = await client.notebooks.get(NOTEBOOK_ID)
        infographic = await client.artifacts.create_infographic(
            notebook_id=NOTEBOOK_ID,
            prompt=prompt,
            orientation="portrait",
        )
        await infographic.download(output_path)
    return output_path

def resize_for_instagram(input_path, output_path):
    img = Image.open(input_path).convert("RGB")
    img.thumbnail((1080, 1350), Image.LANCZOS)
    canvas = Image.new("RGB", (1080, 1350), (255, 255, 255))
    canvas.paste(img, ((1080 - img.width) // 2, (1350 - img.height) // 2))
    canvas.save(output_path, "JPEG", quality=95)
    return output_path

def upload_image(image_path):
    imgbb_key = os.environ["IMGBB_API_KEY"]
    with open(image_path, "rb") as f:
        r = requests.post("https://api.imgbb.com/1/upload", params={"key": imgbb_key}, files={"image": f}, timeout=60)
    r.raise_for_status()
    return r.json()["data"]["url"]

def post_to_instagram(image_url, caption):
    base = f"https://graph.facebook.com/v19.0/{IG_USER_ID}"
    r = requests.post(f"{base}/media", params={"image_url": image_url, "caption": caption, "access_token": IG_ACCESS_TOKEN}, timeout=30)
    r.raise_for_status()
    container_id = r.json()["id"]
    time.sleep(5)
    r = requests.post(f"{base}/media_publish", params={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN}, timeout=30)
    r.raise_for_status()
    print(f"Posted! ID: {r.json()['id']}")

async def main():
    weekday = datetime.utcnow().weekday()
    cookies_json = os.environ["NOTEBOOKLM_COOKIES"]
    with tempfile.TemporaryDirectory() as tmp:
        storage_path = Path(tmp) / "storage.json"
        storage_path.write_text(cookies_json)
        raw = f"{tmp}/raw.png"
        final = f"{tmp}/final.jpg"
        await generate_infographic(str(storage_path), raw)
        resize_for_instagram(raw, final)
        url = upload_image(final)
        caption = CAPTIONS.get(weekday, CAPTIONS[0])
        post_to_instagram(url, caption)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
