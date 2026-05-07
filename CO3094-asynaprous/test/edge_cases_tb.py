import socket
import json
import argparse
import time


def send_raw_http(host, port, request_bytes):
    """Sends raw bytes to the server and cleanly reads the response."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(3.0)
        try:
            s.connect((host, port))
            s.sendall(request_bytes)

            response = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:  # Socket closed by server
                    break
                response += chunk
        except ConnectionRefusedError:
            return "ERROR: Connection Refused", ""
        except Exception as e:
            return f"ERROR: {str(e)}", ""

    # Safely decode and split headers from body
    decoded_resp = response.decode("utf-8", errors="ignore")
    if "\r\n\r\n" in decoded_resp:
        headers, body = decoded_resp.split("\r\n\r\n", 1)
    else:
        headers, body = decoded_resp, ""

    return headers, body


def run_advanced_tests(app_port, proxy_port):
    APP_HOST = "127.0.0.1"
    print(f"🚀 Starting Advanced Edge-Case Testbench\n")
    print(
        f"📡 Targeting App: {APP_HOST}:{app_port} | Targeting Proxy: {APP_HOST}:{proxy_port}\n"
    )

    # =====================================================================
    # TEST 4: Tracker Node Registration (Client-Server Paradigm)
    # =====================================================================
    print("--- TEST 4: Tracker Peer Registration ---")

    submit_body = json.dumps(
        {"username": "DemoPeer99", "ip": "192.168.1.50", "port": 5555}
    )

    req_submit = (
        f"POST /submit-info HTTP/1.1\r\n"
        f"Host: {APP_HOST}:{app_port}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(submit_body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{submit_body}"
    ).encode("utf-8")

    headers_submit, body_submit = send_raw_http(APP_HOST, app_port, req_submit)

    # Wait a tiny bit to ensure the backend writes to tracker.json safely
    time.sleep(0.1)

    req_get = (
        f"GET /get-list HTTP/1.1\r\n"
        f"Host: {APP_HOST}:{app_port}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8")

    headers_get, body_get = send_raw_http(APP_HOST, app_port, req_get)

    if "DemoPeer99" in body_get and "192.168.1.50" in body_get:
        print("✅ [PASS] Tracker successfully registered and listed the new peer.")
    else:
        print("❌ [FAIL] Tracker did not return the registered peer. Body Response:")
        print(body_get)

    # =====================================================================
    # TEST 5: Case-Insensitive Header Parsing (Protocol Compliance)
    # =====================================================================
    print("\n--- TEST 5: Case-Insensitive Header Stress Test ---")

    weird_headers_body = json.dumps(
        {"channel": "general", "sender": "hacker", "message": "hello"}
    )

    req_weird = (
        f"POST /broadcast-peer HTTP/1.1\r\n"
        f"Host: {APP_HOST}:{app_port}\r\n"
        f"cOoKiE: session_id=admin\r\n"
        f"AuThOrIzAtIoN: Bearer mock_token\r\n"
        f"cOnTeNt-tYpE: application/json\r\n"
        f"CoNtEnT-lEnGtH: {len(weird_headers_body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{weird_headers_body}"
    ).encode("utf-8")

    headers_weird, body_weird = send_raw_http(APP_HOST, app_port, req_weird)

    if "200 OK" in headers_weird and "broadcast complete" in body_weird:
        print("✅ [PASS] Server correctly parsed weirdly capitalized HTTP headers.")
    elif "401" in headers_weird or "Missing Cookie" in body_weird:
        print(
            "❌ [FAIL] Server failed to parse case-insensitive headers (It couldn't find 'cOoKiE'). Response:"
        )
        print(headers_weird)
        print(body_weird)
    else:
        print("⚠️  [WARN] Unexpected response:")
        print(headers_weird)

    # =====================================================================
    # TEST 6: Proxy 404 Routing (Testing daemon/proxy.py logic)
    # =====================================================================
    print("\n--- TEST 6: Proxy Unknown Host Rejection ---")

    req_proxy = (
        f"GET / HTTP/1.1\r\n"
        f"Host: totally.fake.domain.local\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8")

    headers_proxy, body_proxy = send_raw_http(APP_HOST, proxy_port, req_proxy)

    if "ERROR" in headers_proxy:
        print(
            f"⚠️  [SKIP] Proxy server does not seem to be running on port {proxy_port}."
        )
    elif "404 Not Found" in headers_proxy:
        print(
            "✅ [PASS] Proxy successfully rejected an unknown Host header with a 404."
        )
    else:
        print("❌ [FAIL] Proxy did not return a 404 for an unknown host. Headers:")
        print(headers_proxy)

    # =====================================================================
    # TEST 7: Malformed Request (Missing Host Header)
    # =====================================================================
    print("\n--- TEST 7: Proxy Missing Host Header ---")

    req_malformed = (f"GET / HTTP/1.1\r\n" f"Connection: close\r\n\r\n").encode("utf-8")

    headers_malformed, body_malformed = send_raw_http(
        APP_HOST, proxy_port, req_malformed
    )

    if "ERROR" in headers_malformed:
        print(
            f"⚠️  [SKIP] Proxy server does not seem to be running on port {proxy_port}."
        )
    elif "400 Bad Request" in headers_malformed or "404 Not Found" in headers_malformed:
        print("✅ [PASS] Proxy safely handled a missing Host header without crashing.")
    else:
        print(
            "❌ [FAIL] Proxy failed to handle the missing Host header safely. Headers:"
        )
        print(headers_malformed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Advanced Testbench")
    # Update default ports here if your setup uses different ones
    parser.add_argument(
        "--app-port", type=int, default=9000, help="Port of the sample app"
    )
    parser.add_argument(
        "--proxy-port", type=int, default=8080, help="Port of the proxy server"
    )
    args = parser.parse_args()

    run_advanced_tests(args.app_port, args.proxy_port)
