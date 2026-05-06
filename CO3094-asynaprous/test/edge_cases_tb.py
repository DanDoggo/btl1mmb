import socket
import json
import argparse

def send_raw_http(host, port, request_bytes):
    """Helper function to send raw bytes to the specified server/proxy."""
    response = b"" # FIXED: Initialized before the try block
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2.0)
        try:
            s.connect((host, port))
            s.sendall(request_bytes)
            
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response += chunk
            return response.decode('utf-8', errors='ignore')
        except ConnectionRefusedError:
            return "ERROR: Connection Refused"
        except socket.timeout:
            if not response:
                return f"ERROR: Connection Timed Out to {host}:{port}"
            return response.decode('utf-8', errors='ignore')

def run_advanced_tests(app_port, proxy_port):
    APP_HOST = "127.0.0.1" 
    print(f"🚀 Starting Advanced Edge-Case Testbench\n")
    print(f"📡 Targeting App: {APP_HOST}:{app_port} | Targeting Proxy: {APP_HOST}:{proxy_port}\n")

    # =====================================================================
    # TEST 4: Tracker Node Registration (Client-Server Paradigm)
    # =====================================================================
    print("--- TEST 4: Tracker Peer Registration ---")
    
    submit_body = json.dumps({"username": "DemoPeer99", "ip": "192.168.1.50", "port": "5555"})
    
    req_submit = (
        f"POST /submit-info HTTP/1.1\r\n"
        f"Host: {APP_HOST}:{app_port}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(submit_body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{submit_body}"
    ).encode('utf-8')

    resp_submit = send_raw_http(APP_HOST, app_port, req_submit)
    
    req_get = (
        f"GET /get-list HTTP/1.1\r\n"
        f"Host: {APP_HOST}:{app_port}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode('utf-8')

    resp_get = send_raw_http(APP_HOST, app_port, req_get)

    if "DemoPeer99" in resp_get and "192.168.1.50" in resp_get:
        print("✅ [PASS] Tracker successfully registered and listed the new peer.")
    else:
        print("❌ [FAIL] Tracker did not return the registered peer. Response:")
        print(resp_get.split("\r\n\r\n")[-1])


    # =====================================================================
    # TEST 5: Case-Insensitive Header Parsing (Protocol Compliance)
    # =====================================================================
    print("\n--- TEST 5: Case-Insensitive Header Stress Test ---")
    
    weird_headers_body = json.dumps({"channel": "general", "sender": "hacker", "message": "hello"})
    
    req_weird = (
        f"POST /broadcast-peer HTTP/1.1\r\n"
        f"Host: {APP_HOST}:{app_port}\r\n"
        f"cOoKiE: session_id=testuser\r\n"
        f"AuThOrIzAtIoN: Bearer mock_token\r\n"
        f"cOnTeNt-tYpE: application/json\r\n"
        f"CoNtEnT-lEnGtH: {len(weird_headers_body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{weird_headers_body}"
    ).encode('utf-8')

    resp_weird = send_raw_http(APP_HOST, app_port, req_weird)

    if "broadcast complete" in resp_weird:
        print("✅ [PASS] Server correctly parsed weirdly capitalized HTTP headers.")
    elif "Missing Cookie" in resp_weird or "401" in resp_weird:
        print("❌ [FAIL] Server failed to parse case-insensitive headers. Response:")
        try:
            print(resp_weird.split("\r\n\r\n")[1])
        except IndexError:
            print(resp_weird)
    else:
        print("⚠️  [WARN] Unexpected response. Response:")
        print(resp_weird)


    # =====================================================================
    # TEST 6: Proxy 404 Routing (Testing daemon/proxy.py logic)
    # =====================================================================
    print("\n--- TEST 6: Proxy Unknown Host Rejection ---")
    
    req_proxy = (
        f"GET / HTTP/1.1\r\n"
        f"Host: totally.fake.domain.local\r\n"
        f"Connection: close\r\n\r\n"
    ).encode('utf-8')

    resp_proxy = send_raw_http(APP_HOST, proxy_port, req_proxy)

    if "ERROR: Connection Refused" in resp_proxy or "ERROR: Connection Timed Out" in resp_proxy:
        print(f"⚠️  [SKIP] Proxy server does not seem to be running on port {proxy_port}.")
    elif "404 Not Found" in resp_proxy:
        print("✅ [PASS] Proxy successfully rejected an unknown Host header with a 404.")
    else:
        print("❌ [FAIL] Proxy did not return a 404 for an unknown host. Response:")
        print(resp_proxy)


    # =====================================================================
    # TEST 7: Malformed Request (Missing Host Header)
    # =====================================================================
    print("\n--- TEST 7: Proxy Missing Host Header ---")
    
    req_malformed = (
        f"GET / HTTP/1.1\r\n"
        f"Connection: close\r\n\r\n"
    ).encode('utf-8')

    resp_malformed = send_raw_http(APP_HOST, proxy_port, req_malformed)

    if "ERROR: Connection Refused" in resp_malformed or "ERROR: Connection Timed Out" in resp_malformed:
        print(f"⚠️  [SKIP] Proxy server does not seem to be running on port {proxy_port}.")
    elif "400 Bad Request" in resp_malformed or "404 Not Found" in resp_malformed:
        print("✅ [PASS] Proxy safely handled a missing Host header without crashing.")
    else:
        print("❌ [FAIL] Proxy failed to handle the missing Host header safely. Response:")
        print(resp_malformed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Advanced Testbench')
    parser.add_argument('--app-port', type=int, default=8001, help='Port of the sample app')
    parser.add_argument('--proxy-port', type=int, default=8080, help='Port of the proxy server')
    args = parser.parse_args()
    
    run_advanced_tests(args.app_port, args.proxy_port)