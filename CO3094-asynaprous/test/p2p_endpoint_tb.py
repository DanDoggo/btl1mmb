import socket
import json

def send_raw_http(host, port, request_bytes):
    """Cleanly sends raw bytes and returns the headers and body."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2.0)
        try:
            s.connect((host, port))
            s.sendall(request_bytes)
            
            response = b""
            while True:
                chunk = s.recv(4096)
                if not chunk: 
                    break
                response += chunk
        except Exception as e:
            return f"ERROR: {str(e)}", ""
            
    decoded_resp = response.decode('utf-8', errors='ignore')
    if "\r\n\r\n" in decoded_resp:
        headers, body = decoded_resp.split("\r\n\r\n", 1)
    else:
        headers, body = decoded_resp, ""
        
    return headers, body

def run_p2p_tests():
    APP_HOST = "127.0.0.1" 
    APP_PORT = 9000
    
    print(f"🚀 Starting Final P2P & Channel API Testbench against {APP_HOST}:{APP_PORT}\n")

    # =====================================================================
    # TEST 8: Channel Management (/add-list)
    # =====================================================================
    print("--- TEST 8: Local Channel Creation (/add-list) ---")
    
    add_body = json.dumps({"channel": "project_group_1"})
    
    req_add = (
        f"POST /add-list HTTP/1.1\r\n"
        f"Host: {APP_HOST}:{APP_PORT}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(add_body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{add_body}"
    ).encode('utf-8')

    headers_add, body_add = send_raw_http(APP_HOST, APP_PORT, req_add)

    if "success" in body_add and "project_group_1" in body_add:
        print("✅ [PASS] Server successfully created and tracked the new local channel.")
    else:
        print("❌ [FAIL] Server failed to create the channel. Response:")
        print(body_add)

    # =====================================================================
    # TEST 9: P2P Handshake Protocol (/connect-peer)
    # =====================================================================
    print("\n--- TEST 9: P2P Direct Handshake (/connect-peer) ---")
    
    connect_body = json.dumps({"sender": "TestBenchNode"})
    
    req_connect = (
        f"POST /connect-peer HTTP/1.1\r\n"
        f"Host: {APP_HOST}:{APP_PORT}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(connect_body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{connect_body}"
    ).encode('utf-8')

    headers_connect, body_connect = send_raw_http(APP_HOST, APP_PORT, req_connect)

    if "connected" in body_connect and "Handshake accepted" in body_connect:
        print("✅ [PASS] Server successfully processed the P2P handshake.")
    else:
        print("❌ [FAIL] Server rejected the P2P handshake. Response:")
        print(body_connect)

    # =====================================================================
    # TEST 10: True Direct Peer Messaging (/send-peer)
    # =====================================================================
    print("\n--- TEST 10: True Direct P2P Messaging (/send-peer) ---")
    
    send_body = json.dumps({
        "channel": "@admin_testbench", 
        "sender": "TestBenchNode", 
        "message": "This is a direct message bypassing the tracker!"
    })
    
    req_send = (
        f"POST /send-peer HTTP/1.1\r\n"
        f"Host: {APP_HOST}:{APP_PORT}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(send_body)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{send_body}"
    ).encode('utf-8')

    headers_send, body_send = send_raw_http(APP_HOST, APP_PORT, req_send)

    if "delivered" in body_send:
        print("✅ [PASS] Server accepted the direct P2P message injection!")
    else:
        print("❌ [FAIL] Server failed to accept the direct message. Response:")
        print(body_send)
        
    # --- BONUS VERIFICATION: Did it actually save to memory? ---
    req_verify = (
        f"GET /get-messages HTTP/1.1\r\n"
        f"Host: {APP_HOST}:{APP_PORT}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode('utf-8')
    
    _, body_verify = send_raw_http(APP_HOST, APP_PORT, req_verify)
    
    if "@admin_testbench" in body_verify and "bypassing the tracker" in body_verify:
        print("✅ [PASS] Bonus: Verified the direct message was successfully written to the chat memory!")
    else:
        print("❌ [FAIL] Bonus: The message was accepted but not saved to memory.")

if __name__ == "__main__":
    run_p2p_tests()