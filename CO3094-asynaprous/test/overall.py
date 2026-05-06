import socket
import base64
import json

# === CONFIGURATION ===
# Change these if you are testing through the proxy or on a VM IP
HOST = "127.0.0.1" 
PORT = 8001  # Default port from start_sampleapp.py

def send_raw_http(request_bytes):
    """Helper function to send raw bytes to the server and return the response."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2.0)
        s.connect((HOST, PORT))
        s.sendall(request_bytes)
        
        response = b""
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response += chunk
        except socket.timeout:
            pass # Timeout reached, assuming server sent everything
            
    return response.decode('utf-8', errors='ignore')

def run_tests():
    print(f"🚀 Starting Authentication Testbench against {HOST}:{PORT}\n")

    # =====================================================================
    # TEST 1: RFC 2617 Basic Authentication (Testing request.py parser)
    # =====================================================================
    print("--- TEST 1: RFC 2617 Basic Authentication ---")
    
    # 1. Manually encode the credentials
    username, password = "admin", "secret"
    auth_string = f"{username}:{password}"
    b64_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    
    body = json.dumps({"test": "basic_auth_check"})
    
    req_1 = (
        f"POST /echo HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        f"Authorization: Basic {b64_auth}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{body}"
    ).encode('utf-8')

    resp_1 = send_raw_http(req_1)
    
    # Check if the server accepted it (Assuming /echo returns 200 OK)
    if "200 OK" in resp_1:
        print("✅ [PASS] Server accepted Basic Auth header.")
    else:
        print("❌ [FAIL] Basic Auth failed. Response:")
        print(resp_1.split("\r\n\r\n")[0]) # Print headers for debugging


    # =====================================================================
    # TEST 2: RFC 6265 Cookie Issuance (Testing /login endpoint)
    # =====================================================================
    print("\n--- TEST 2: RFC 6265 Cookie Issuance ---")
    
    login_body = json.dumps({"username": "testuser"})
    
    req_2 = (
        f"POST /login HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(login_body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{login_body}"
    ).encode('utf-8')

    resp_2 = send_raw_http(req_2)
    
    # Extract the cookie from the response
    cookie_value = None
    for line in resp_2.splitlines():
        if line.lower().startswith("set-cookie:"):
            cookie_value = line.split(":", 1)[1].split(";")[0].strip()
            break

    if cookie_value and "session_id=testuser" in cookie_value:
        print(f"✅ [PASS] Server issued correct cookie: {cookie_value}")
    else:
        print("❌ [FAIL] Failed to receive Set-Cookie header. Response:")
        print(resp_2.split("\r\n\r\n")[0])


    # =====================================================================
    # TEST 3: Access Control with Cookie & Bearer (Testing /broadcast-peer)
    # =====================================================================
    print("\n--- TEST 3: Access Control (Cookie Verification) ---")
    
    if not cookie_value:
        print("⏭️  [SKIP] Skipping Test 3 because Test 2 failed to get a cookie.")
        return

    broadcast_body = json.dumps({
        "channel": "general", 
        "sender": "testuser", 
        "message": "Testing access control!"
    })
    
    req_3 = (
        f"POST /broadcast-peer HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        f"Cookie: {cookie_value}\r\n"
        f"Authorization: Bearer mock_token_for_assignment\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(broadcast_body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{broadcast_body}"
    ).encode('utf-8')

    resp_3 = send_raw_http(req_3)

    if "200 OK" in resp_3 and "broadcast complete" in resp_3:
        print("✅ [PASS] Server validated Cookie and Bearer token successfully!")
    elif "401 Unauthorized" in resp_3 or "Missing Cookie" in resp_3:
        print("❌ [FAIL] Server rejected the credentials. Response:")
        print(resp_3.split("\r\n\r\n")[1]) # Print the JSON error
    else:
        print("⚠️  [WARN] Unexpected response:")
        print(resp_3)

if __name__ == "__main__":
    run_tests()