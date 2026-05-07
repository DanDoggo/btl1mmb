import socket
import base64
import json
import time

# === CONFIGURATION ===
HOST = "127.0.0.1"
PORT = 9000  # Ensure this matches your running server instance

# Use credentials that actually exist in your db/auth_db.json
TEST_USER = "admin"
TEST_PASS = "admin"


def send_raw_http(request_bytes):
    """Sends raw bytes to the server and cleanly reads the response."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(3.0)
        try:
            s.connect((HOST, PORT))
            s.sendall(request_bytes)

            response = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:  # Socket closed by server (Connection: close)
                    break
                response += chunk
        except Exception as e:
            return f"ERROR: {str(e)}"

    # Safely decode and split headers from body
    decoded_resp = response.decode("utf-8", errors="ignore")
    if "\r\n\r\n" in decoded_resp:
        headers, body = decoded_resp.split("\r\n\r\n", 1)
    else:
        headers, body = decoded_resp, ""

    return headers, body


def run_tests():
    print(f"🚀 Starting Security & RFC Compliance Testbench against {HOST}:{PORT}\n")

    # =====================================================================
    # TEST 1: RFC 2617 Basic Authentication Header Parsing
    # =====================================================================
    print("--- TEST 1: RFC 2617 Basic Authentication Format ---")

    auth_string = f"{TEST_USER}:{TEST_PASS}"
    b64_auth = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")

    # We send this to /login just to see if the parser survives the Authorization header
    body_1 = json.dumps({"username": TEST_USER, "password": TEST_PASS})
    req_1 = (
        f"POST /login HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        f"Authorization: Basic {b64_auth}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body_1)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{body_1}"
    ).encode("utf-8")

    headers_1, body_1_resp = send_raw_http(req_1)

    if "200 OK" in headers_1:
        print(
            "✅ [PASS] Server accepted and parsed the Basic Auth header without crashing."
        )
    else:
        print("❌ [FAIL] Server rejected the request. Headers:")
        print(headers_1)

    # =====================================================================
    # TEST 2: RFC 6265 Cookie Issuance (Testing /login)
    # =====================================================================
    print("\n--- TEST 2: RFC 6265 Cookie Issuance ---")

    login_body = json.dumps({"username": TEST_USER, "password": TEST_PASS})
    req_2 = (
        f"POST /login HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(login_body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{login_body}"
    ).encode("utf-8")

    headers_2, body_2_resp = send_raw_http(req_2)

    cookie_value = None
    for line in headers_2.splitlines():
        if line.lower().startswith("set-cookie:"):
            # Extract exactly the 'session_id=admin' part
            cookie_value = line.split(":", 1)[1].split(";")[0].strip()
            break

    if cookie_value and f"session_id={TEST_USER}" in cookie_value:
        print(f"✅ [PASS] Server issued valid RFC-compliant cookie: {cookie_value}")
    else:
        print("❌ [FAIL] Failed to receive Set-Cookie header. Headers received:")
        print(headers_2)

    # =====================================================================
    # TEST 3: Access Control - Valid Cookie (Testing /broadcast-peer)
    # =====================================================================
    print("\n--- TEST 3: Access Control (Cookie Verification - POSITIVE) ---")

    if not cookie_value:
        print("⏭️  [SKIP] Skipping Test 3 because Test 2 failed to get a cookie.")
    else:
        broadcast_body = json.dumps(
            {
                "channel": "general",
                "sender": TEST_USER,
                "message": "Testing access control!",
            }
        )

        req_3 = (
            f"POST /broadcast-peer HTTP/1.1\r\n"
            f"Host: {HOST}:{PORT}\r\n"
            f"Cookie: {cookie_value}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(broadcast_body)}\r\n"
            f"Connection: close\r\n\r\n"
            f"{broadcast_body}"
        ).encode("utf-8")

        headers_3, body_3_resp = send_raw_http(req_3)

        if "200 OK" in headers_3:
            print("✅ [PASS] Server validated the Cookie and allowed the broadcast!")
        else:
            print("❌ [FAIL] Server rejected the valid cookie. Response:")
            print(headers_3)

    # =====================================================================
    # TEST 4: RFC 7235 Access Control - Missing Cookie (Security Audit)
    # =====================================================================
    print("\n--- TEST 4: RFC 7235 Access Control (Security Audit - NEGATIVE) ---")

    req_4 = (
        f"POST /broadcast-peer HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        # INTENTIONALLY OMITTING THE COOKIE HEADER
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(broadcast_body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{broadcast_body}"
    ).encode("utf-8")

    headers_4, body_4_resp = send_raw_http(req_4)

    if "401 Unauthorized" in headers_4:
        print(
            "✅ [PASS] Server correctly blocked the request when missing a cookie (401 Unauthorized)!"
        )
    else:
        print(
            "❌ [FAIL] SECURITY FLAW! Server allowed access without a cookie. Response:"
        )
        print(headers_4)

    print("\n🎉 Testbench Execution Complete!")


if __name__ == "__main__":
    run_tests()
