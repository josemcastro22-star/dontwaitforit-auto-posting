import os
import sys
import requests

GRAPH_VERSION = "v25.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"Missing env var: {name}", file=sys.stderr)
        sys.exit(1)
    return val

def main():
    ig_user_id = require_env("IG_USER_ID")
    access_token = require_env("IG_ACCESS_TOKEN")

    # Simple sanity check call: fetch username
    url = f"{GRAPH_BASE}/{ig_user_id}"
    params = {
        "fields": "username",
        "access_token": access_token,
    }

    r = requests.get(url, params=params, timeout=30)
    print("GET", r.url)
    print("STATUS", r.status_code)
    print(r.text)

    if r.status_code != 200:
        sys.exit(2)

    print("✅ Instagram API connectivity looks good.")

if __name__ == "__main__":
    main()
