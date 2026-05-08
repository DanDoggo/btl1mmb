#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.proxy
~~~~~~~~~~~~~~~~~

This module implements a simple proxy server using Python's socket and threading libraries.
It routes incoming HTTP requests to backend services based on hostname mappings and returns
the corresponding responses to clients.

Requirement:
-----------------
- socket: provides socket networking interface.
- threading: enables concurrent client handling via threads.
- response: customized :class: `Response <Response>` utilities.
- httpadapter: :class: `HttpAdapter <HttpAdapter >` adapter for HTTP request processing.
- dictionary: :class: `CaseInsensitiveDict <CaseInsensitiveDict>` for managing headers and cookies.

"""

import json
import socket
import threading
from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

_rr_state = {}

#: A dictionary mapping hostnames to backend IP and port tuples.
#: Used to determine routing targets for incoming requests.
PROXY_PASS = {
    "192.168.56.114:8080": ("192.168.56.114", 9000),
    "app1.local": ("192.168.56.114", 9001),
    "app2.local": ("192.168.56.114", 9002),
}


def forward_request(host, port, request):
    """
    Forward an HTTP request to a backend server and retrieve the response.

    :param host: IP address of the backend server.
    :type host: str
    :param port: Port number of the backend server.
    :type port: int
    :param request: Incoming HTTP request.
    :type request: bytes
    :return: Raw HTTP response from the backend server. If the connection fails, returns a 404.
    :rtype: bytes
    """

    backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        backend.connect((host, port))
        backend.sendall(request)
        response = b""
        while True:
            chunk = backend.recv(4096)
            if not chunk:
                break
            response += chunk
        return response
    except socket.error as e:
        print("Socket error: {}".format(e))
        return (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 Not Found"
        ).encode("utf-8")


def resolve_routing_policy(hostname, routes):
    """
    Handle a routing policy to return the matching proxy_pass and custom headers.

    It determines the target backend to forward the request to.

    :param hostname: The hostname extracted from the request Host header.
    :type hostname: str
    :param routes: Dictionary mapping hostnames to backend locations.
    :type routes: dict
    :return: Target host, target port, and any custom headers to inject.
    :rtype: tuple
    """
    # --- THE FIX: Unpack 3 values, providing a default empty dict for headers ---
    proxy_map, policy, set_headers = routes.get(hostname, ([], "round-robin", {}))

    proxy_host = ""
    proxy_port = "9000"
    if isinstance(proxy_map, list):
        if len(proxy_map) == 0:
            proxy_host, proxy_port = None, None
        elif len(proxy_map) == 1:
            proxy_host, proxy_port = proxy_map[0].split(":", 1)
        else:
            if policy == "round-robin":
                global _rr_state
                idx = _rr_state.get(hostname, 0)
                proxy_host, proxy_port = proxy_map[idx].split(":", 1)
                _rr_state[hostname] = (idx + 1) % len(proxy_map)
            else:
                proxy_host, proxy_port = proxy_map[0].split(":", 1)
    else:
        proxy_host, proxy_port = proxy_map.split(":", 1)

    # Return the set_headers so handle_client can use them
    return proxy_host, proxy_port, set_headers


def handle_client(ip, port, conn, addr, routes):
    """
    Handle an individual client connection by parsing the request,
    determining the target backend, and forwarding the request.

    The handler extracts the Host header from the request to
    match the hostname against known routes. In the matching
    condition, it forwards the request to the appropriate backend.
    The handler sends the backend response back to the client or
    returns 404 if the hostname is unreachable or is not recognized.

    :param ip: IP address of the proxy server.
    :type ip: str
    :param port: Port number of the proxy server.
    :type port: int
    :param conn: Client connection socket.
    :type conn: socket.socket
    :param addr: Client address tuple (IP, port).
    :type addr: tuple
    :param routes: Dictionary mapping hostnames and location.
    :type routes: dict
    """
    # --- THE FIX: BYTE-SAFE ROBUST READING ---
    raw_request = b""

    # 1. Read until the end of the HTTP headers
    while b"\r\n\r\n" not in raw_request:
        chunk = conn.recv(1024)
        if not chunk:
            break
        raw_request += chunk

    if not raw_request:
        conn.close()
        return

    header_data, separator, body_data = raw_request.partition(b"\r\n\r\n")
    header_text = header_data.decode("utf-8", errors="ignore")

    # Extract Hostname and Content-Length
    hostname = None
    content_length = 0
    for line in header_text.split("\r\n"):
        if line.lower().startswith("host:"):
            hostname = line.split(":", 1)[1].strip()
        elif line.lower().startswith("content-length:"):
            try:
                content_length = int(line.split(":")[1].strip())
            except ValueError:
                pass

    if not hostname:
        conn.sendall(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
        conn.close()
        return

    # Read the remaining body based on Content-Length
    while len(body_data) < content_length:
        chunk = conn.recv(4096)
        if not chunk:
            break
        body_data += chunk

    # Reassemble the raw request as bytes
    full_raw_request = header_data + separator + body_data
    # -----------------------------------------

    # === THE FIX: DYNAMIC PROXY REGISTRATION ===
    request_line = header_text.split("\r\n")[0]
    if "POST /proxy-register HTTP" in request_line:
        try:
            body_json = json.loads(body_data.decode("utf-8"))

            # ĐỈNH CAO Ở ĐÂY: Không tin tưởng IP từ JS gửi lên,
            # Proxy tự động bắt IP thật của Laptop đang kết nối thông qua socket!
            peer_ip = addr[0]
            peer_port = str(body_json.get("port", "9000"))
            target_host = hostname

            print(
                f"[Proxy] DYNAMIC REGISTRATION: Allowing {peer_ip}:{peer_port} into Proxy Pool!"
            )

            # Nếu host chưa tồn tại trong RAM của Proxy, tạo mới
            if target_host not in routes:
                routes[target_host] = ([], "round-robin", {})

            proxy_map, policy, custom_headers = routes[target_host]
            new_backend = f"{peer_ip}:{peer_port}"

            # Xử lý an toàn nếu proxy_map đang là chuỗi (chỉ có 1 backend gốc)
            if isinstance(proxy_map, str):
                proxy_map = [proxy_map]

            # Thêm IP mới vào danh sách cho phép
            if new_backend not in proxy_map:
                proxy_map.append(new_backend)

            # Cập nhật lại bộ nhớ định tuyến của Proxy
            routes[target_host] = (proxy_map, policy, custom_headers)

            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                "Connection: close\r\n\r\n"
                '{"status": "Dynamic Proxy Updated"}'
            ).encode("utf-8")
        except Exception as e:
            response = (
                f"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n{str(e)}".encode(
                    "utf-8"
                )
            )

        conn.sendall(response)
        conn.close()
        return
    # =========================================

    resolved_host, resolved_port, set_headers = resolve_routing_policy(hostname, routes)

    # --- THE FIX: Clean Type Checking for the Port ---
    if resolved_host is None or resolved_port is None:
        resolved_host = None
    else:
        try:
            resolved_port = int(resolved_port)
        except ValueError:
            resolved_host = None
    # -------------------------------------------------

    if resolved_host:
        print(
            "[Proxy] Forwarding {} to {}:{}".format(
                hostname, resolved_host, resolved_port
            )
        )

        # --- THE FIX: Safe Header Modification ---
        if set_headers:
            lines = header_text.split("\r\n")
            request_line = lines[0]
            original_headers = lines[1:]

            new_headers = []
            keys_to_replace = {k.lower(): k for k in set_headers.keys()}

            for line in original_headers:
                if not line.strip():
                    continue
                key, val = line.split(":", 1)
                lower_key = key.strip().lower()

                if lower_key in keys_to_replace:
                    target_key = keys_to_replace[lower_key]
                    new_val = set_headers[target_key]
                    if new_val == "$host":
                        new_val = hostname
                    new_headers.append(f"{target_key}: {new_val}")
                    del keys_to_replace[lower_key]
                else:
                    new_headers.append(line)

            for lower_key, target_key in keys_to_replace.items():
                new_val = set_headers[target_key]
                if new_val == "$host":
                    new_val = hostname
                new_headers.append(f"{target_key}: {new_val}")

            # Reconstruct headers as text, encode to bytes, add raw body
            new_header_text = (
                request_line + "\r\n" + "\r\n".join(new_headers) + "\r\n\r\n"
            )
            full_raw_request = new_header_text.encode("utf-8") + body_data
        # ------------------------------------------

        # Change forward_request to accept bytes!
        response = forward_request(resolved_host, resolved_port, full_raw_request)
    else:
        response = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 Not Found"
        ).encode("utf-8")

    conn.sendall(response)
    conn.close()


def run_proxy(ip, port, routes):
    """
    Start the proxy server and listen for incoming connections.

    The process binds the proxy server to the specified IP and port.
    On each incoming connection, it accepts the connection and
    spawns a new thread for each client using `handle_client`.

    :param ip: IP address to bind the proxy server.
    :type ip: str
    :param port: Port number to listen on.
    :type port: int
    :param routes: Dictionary mapping hostnames and location.
    :type routes: dict
    """

    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print("[Proxy] Listening on IP {} port {}".format(ip, port))
        while True:
            conn, addr = proxy.accept()
            # Implement the step of the client incoming connection
            # using multi-thread programming with the provided handle_client routine
            client_thread = threading.Thread(
                target=handle_client, args=(ip, port, conn, addr, routes)
            )
            client_thread.daemon = True
            client_thread.start()
    except socket.error as e:
        print("Socket error: {}".format(e))


def create_proxy(ip, port, routes):
    """
    Entry point for launching the proxy server.

    :param ip: IP address to bind the proxy server.
    :type ip: str
    :param port: Port number to listen on.
    :type port: int
    :param routes: Dictionary mapping hostnames and location.
    :type routes: dict
    """

    run_proxy(ip, port, routes)
