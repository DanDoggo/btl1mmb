import urllib.request
import urllib.error
import json
import time


def send_post(port, path, data, sender_name="Alice"):
    """Helper to send POST requests with proper Auth and Cookie headers."""
    url = f"http://127.0.0.1:{port}{path}"

    # FIXED: Added the required Cookie header to bypass your security checks
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {sender_name}-Test-Token",
        "Cookie": f"session_id={sender_name}",
    }

    req = urllib.request.Request(
        url, data=json.dumps(data).encode("utf-8"), headers=headers
    )

    try:
        response = urllib.request.urlopen(req)
        resp_body = response.read().decode("utf-8", errors="ignore")
        print(f"✅ [SUCCESS] POST {path} to Port {port} | Server Reply: {resp_body}")
    except urllib.error.HTTPError as e:
        # FIXED: Read the actual error body from the server (e.g., "Missing Cookie")
        err_body = e.read().decode("utf-8", errors="ignore")
        print(f"❌ [FAIL] POST {path} to Port {port} | HTTP {e.code}: {err_body}")
    except urllib.error.URLError as e:
        print(
            f"⚠️  [OFFLINE] Port {port} is not running! Start start_sampleapp.py on this port."
        )
    except Exception as e:
        print(f"❌ [ERROR] POST {path} to Port {port} | {e}")


print("--- 1. REGISTERING PEERS TO THE NETWORK ---")
# Tell Alice (8001) where to find Bob and Charlie
send_post(8001, "/submit-info", {"username": "Bob", "ip": "127.0.0.1", "port": 8002})
send_post(
    8001, "/submit-info", {"username": "Charlie", "ip": "127.0.0.1", "port": 8003}
)

time.sleep(1)  # Brief pause for network stability

print("\n--- 2. SENDING DIRECT P2P BROADCAST ---")
# Alice (8001) initiates a broadcast.
# If successful, watch the terminal windows for 8002 and 8003 to react!
payload = {
    "sender": "Alice",
    "channel": "general",
    "message": "Hello everyone! This is a multi-server P2P test.",
}
send_post(8001, "/broadcast-peer", payload, sender_name="Alice")
