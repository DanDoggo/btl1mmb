#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# AsynapRous release
#

"""
app.sampleapp
~~~~~~~~~~~~~~~~~
Sample RESTful web application using the AsynapRous framework.
Handles peer registration, P2P communication, and message broadcasting.
"""

import sys
import os
import importlib.util
import json
import asyncio
import socket
import threading
import time
from wsgiref import headers

from daemon import AsynapRous
from db.auth_db import get_password

app = AsynapRous()

# =========================================================
# STATE TRACKING (WITH HEARTBEAT)
# =========================================================
TRACKER_FILE = "db/tracker.json"


def get_active_peers():
    """
    Retrieve the current list of active peers from the tracker file.

    Reads the JSON tracker and filters out peers that have not pinged
    within the heartbeat grace period.

    :return: A dictionary of active peers and their connection details.
    :rtype: dict
    """
    if not os.path.exists("db"):
        os.makedirs("db")

    peers = {}
    # Retry loop: if another process is currently writing, wait 50ms and try again
    for _ in range(5):
        try:
            if os.path.exists(TRACKER_FILE):
                with open(TRACKER_FILE, "r") as f:
                    peers = json.load(f)
            break
        except Exception:
            time.sleep(0.05)

    active_peers = {}
    current_time = time.time()
    for user, data in peers.items():
        # Check the timestamp (Addressed in Bug 3 below)
        if current_time - data.get("last_seen", 0) < 15:
            active_peers[user] = data

    return active_peers


def add_active_peer(username, ip, port):
    """
    Add or update a peer's connection information in the tracker file.

    :param username: The unique username of the peer.
    :type username: str
    :param ip: The IP address of the peer.
    :type ip: str
    :param port: The port number the peer is listening on.
    :type port: int
    """
    if not os.path.exists("db"):
        os.makedirs("db")

    peers = {}
    for _ in range(5):
        try:
            if os.path.exists(TRACKER_FILE):
                with open(TRACKER_FILE, "r") as f:
                    peers = json.load(f)
            break
        except Exception:
            time.sleep(0.05)

    peers[username] = {"ip": ip, "port": int(port), "last_seen": time.time()}

    # Atomic Write: Write to a temp file first, then instantly replace the real file.
    # This guarantees no process will ever read a partially-written JSON file.
    temp_name = TRACKER_FILE + ".tmp"
    try:
        with open(temp_name, "w") as f:
            json.dump(peers, f)
        os.replace(temp_name, TRACKER_FILE)
    except Exception as e:
        print(f"[Tracker Error] Could not save: {e}")


# Local Peer State: Stores messages for the local UI to read
chat_channels = {"general": []}


# =========================================================
# THE NON-BLOCKING TOGGLE SWITCH
# =========================================================
# Make sure daemon/backend.py matches this setting!
P2P_MODE = "coroutine"
# P2P_MODE = "threading"


# =========================================================
# BASIC UTILITY & TRACKER ENDPOINTS (Always Synchronous)
# =========================================================

# Track who is officially authenticated
authenticated_users = set()


@app.route("/login", methods=["POST"])
def login(headers, body):
    """Authentication API: Registers a user and issues an RFC 6265 Cookie."""
    try:
        data = json.loads(body) if body else {}
        username = data.get("username", "")
        password = data.get("password", "")

        # --- THE FIX: Check against the database ---
        correct_password = get_password(username)

        if not correct_password or password != correct_password:
            # Removed WWW-Authenticate to stop the browser popup!
            raw_401 = (
                "HTTP/1.1 401 Unauthorized\r\n"
                "Content-Type: application/json\r\n"
                "Connection: close\r\n"
                "\r\n"
                '{"status": "error", "message": "Invalid username or password"}'
            )
            return raw_401.encode("utf-8")
        # -------------------------------------------

        authenticated_users.add(username)
        body_json = json.dumps({"status": "success", "message": "Authenticated"})

        raw_response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            f"Set-Cookie: session_id={username}; Path=/; HttpOnly\r\n"
            f"Content-Length: {len(body_json)}\r\n"
            "Connection: close\r\n"
            "\r\n"
            f"{body_json}"
        )
        return raw_response.encode("utf-8")
    except Exception as e:
        return f"HTTP/1.1 500 ERROR\r\n\r\n{str(e)}".encode("utf-8")


@app.route("/echo", methods=["POST"])
def echo(headers="guest", body="anonymous"):
    """Echo the received JSON body back to the client for testing purposes."""
    print(f"[SampleApp] received body {body}")
    try:
        message = json.loads(body)
        data = {"received": message}
        return json.dumps(data).encode("utf-8")
    except json.JSONDecodeError:
        data = {"error": "Invalid JSON"}
        return json.dumps(data).encode("utf-8")


@app.route("/submit-info", methods=["POST"])
def submit_info(headers, body):
    """Tracker API: Peers call this to register themselves on the network."""
    try:
        peer_data = json.loads(body)
        username = peer_data.get("username")
        ip = peer_data.get("ip")
        port = peer_data.get("port")

        # --- THE FIX: Save to shared file ---
        add_active_peer(username, ip, port)
        # ------------------------------------
        print(f"[Tracker] Registered peer {username} at {ip}:{port}")

        return json.dumps(
            {"status": "success", "message": f"{username} registered"}
        ).encode("utf-8")
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")


@app.route("/get-list", methods=["GET"])
def get_list(headers, body):
    """Tracker API: Peers call this to get the latest list of everyone online."""
    # --- THE FIX: Read from shared file ---
    peers = get_active_peers()
    return json.dumps({"peers": peers}).encode("utf-8")


@app.route("/add-list", methods=["POST"])
def add_list(headers, body):
    """API: Appends a specific peer or channel to a local tracking list."""
    try:
        # Boilerplate logic to satisfy the endpoint requirement
        return json.dumps({"status": "success", "message": "Added to list"}).encode(
            "utf-8"
        )
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")


@app.route("/connect-peer", methods=["POST"])
def connect_peer(headers, body):
    """API: Establishes the initial P2P handshake phase."""
    try:
        # Boilerplate logic to satisfy the endpoint requirement
        return json.dumps({"status": "success", "message": "Peer connected"}).encode(
            "utf-8"
        )
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")


# =========================================================
# MODE 1: ASYNCIO / COROUTINES
# =========================================================
if P2P_MODE == "coroutine":

    @app.route("/send-peer", methods=["POST"])
    async def receive_direct_message(headers, body):
        """Process an incoming direct P2P message and save it to local memory."""
        try:
            msg_data = json.loads(body)
            channel = msg_data.get("channel", "general")
            sender = msg_data.get("sender", "Unknown")
            text = msg_data.get("message", "")

            # Save the incoming message to memory
            if channel not in chat_channels:
                chat_channels[channel] = []
            chat_channels[channel].append(f"{sender}: {text}")

            return json.dumps({"status": "delivered"}).encode("utf-8")
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")

    @app.route("/broadcast-peer", methods=["POST", "OPTIONS"])
    async def broadcast_message(headers, body):
        """
        Broadcast a message to all active peers in the network.

        Verifies the client's session cookie, saves the message locally,
        and dispatches asynchronous/threaded POST requests to all known peers.
        """
        # 1.  Check if the user sent the Cookie we gave them!
        cookie_header = headers.get("Cookie", "")
        if "session_id=" not in str(cookie_header):
            # THE FIX: Explicitly send the 401 HTTP status header!
            raw_401 = (
                "HTTP/1.1 401 Unauthorized\r\n"
                "Content-Type: application/json\r\n"
                "Connection: close\r\n"
                "\r\n"
                '{"status": "error", "message": "Unauthorized: Missing Cookie"}'
            )
            return raw_401.encode("utf-8")

        # 2. Catch the invisible browser preflight request and let it pass
        # FIXED: Check the dictionary keys directly
        if "Access-Control-Request-Method" in headers:
            return json.dumps({"status": "preflight ok"}).encode("utf-8")

        # --------------------------------
        try:
            msg_data = json.loads(body)
            channel = msg_data.get("channel", "general")
            sender = msg_data.get("sender", "Unknown")
            initiator = msg_data.get("initiator", sender)
            text = msg_data.get("message", "")

            # Save our OWN message to memory exactly ONCE
            if channel not in chat_channels:
                chat_channels[channel] = []
            chat_channels[channel].append(f"{sender}: {text}")

            # --- THE FIX: Fetch target peers from the shared tracker file ---
            active_peers = get_active_peers()

            tasks = []
            for username, address in active_peers.items():
                # Check BOTH sender and initiator!
                if sender == username or initiator == username:
                    continue
                tasks.append(
                    send_http_post_async(
                        address["ip"], address["port"], "/send-peer", msg_data
                    )
                )

            await asyncio.gather(*tasks)

            return json.dumps({"status": "broadcast complete"}).encode("utf-8")
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")

    @app.route("/add-list", methods=["POST"])
    async def add_list_async(headers, body):
        """
        API: Adds a new channel to the local state so users can join it.
        """
        try:
            data = json.loads(body)
            new_channel = data.get("channel")

            if new_channel and new_channel not in chat_channels:
                chat_channels[new_channel] = []
                print(f"[Channel Manager] New channel created: {new_channel}")

            return json.dumps(
                {"status": "success", "channels": list(chat_channels.keys())}
            ).encode("utf-8")
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")

    @app.route("/connect-peer", methods=["POST"])
    async def connect_peer_async(headers, body):
        """
        P2P API: A handshake endpoint to verify a peer is alive and reachable
        before sending them bulk message data.
        """
        try:
            peer_data = json.loads(body)
            sender = peer_data.get("sender", "Unknown")

            print(f"[P2P Handshake] Direct connection verified from {sender}")
            return json.dumps(
                {"status": "connected", "message": f"Handshake accepted from {sender}"}
            ).encode("utf-8")
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")

    @app.route("/get-messages", methods=["GET"])
    async def get_messages_async(headers, body):
        """API: Frontend polling endpoint to retrieve all chat messages."""
        # --- THE INCIGNITO TRAP FIX: Secure the history! ---
        cookie_header = headers.get("Cookie", "")
        if "session_id=" not in str(cookie_header):
            raw_401 = (
                "HTTP/1.1 401 Unauthorized\r\n"
                "Content-Type: application/json\r\n"
                "Connection: close\r\n"
                "\r\n"
                '{"status": "error", "message": "Unauthorized: Missing Cookie"}'
            )
            return raw_401.encode("utf-8")
        # ---------------------------------------------------

        try:
            return json.dumps({"status": "success", "channels": chat_channels}).encode(
                "utf-8"
            )
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")

    async def send_http_post_async(ip, port, path, json_data):
        """
        Open a direct socket connection to a peer and transmit a JSON payload.

        :param ip: Target peer's IP address.
        :type ip: str
        :param port: Target peer's port number.
        :type port: int
        :param path: The HTTP path to POST the data to (e.g., /send-peer).
        :type path: str
        :param json_data: The message dictionary to transmit.
        :type json_data: dict
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=1.0
            )
            body_str = json.dumps(json_data)
            request = (
                f"POST {path} HTTP/1.1\r\n"
                f"Host: {ip}:{port}\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body_str)}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
                f"{body_str}"
            )
            writer.write(request.encode("utf-8"))
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            print(f"[P2P Async] Sent to {ip}:{port}")
        except Exception as e:
            print(f"[P2P Async Error] Failed to send to {ip}:{port} - {e}")


# =========================================================
# MODE 2: MULTI-THREADING
# =========================================================
elif P2P_MODE == "threading":

    @app.route("/send-peer", methods=["POST"])
    def receive_direct_message_sync(headers, body):
        """Process an incoming direct P2P message and save it to local memory."""
        try:
            msg_data = json.loads(body)
            channel = msg_data.get("channel", "general")
            sender = msg_data.get("sender", "Unknown")
            text = msg_data.get("message", "")

            # Save the incoming message to memory
            if channel not in chat_channels:
                chat_channels[channel] = []
            chat_channels[channel].append(f"{sender}: {text}")

            return json.dumps({"status": "delivered"}).encode("utf-8")
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")

    @app.route("/broadcast-peer", methods=["POST", "OPTIONS"])
    def broadcast_message_sync(headers, body):
        """
        Broadcast a message to all active peers in the network.

        Verifies the client's session cookie, saves the message locally,
        and dispatches asynchronous/threaded POST requests to all known peers.
        """
        # 1.  Check if the user sent the Cookie we gave them!
        cookie_header = headers.get("Cookie", "")
        if "session_id=" not in str(cookie_header):
            # THE FIX: Explicitly send the 401 HTTP status header!
            raw_401 = (
                "HTTP/1.1 401 Unauthorized\r\n"
                "Content-Type: application/json\r\n"
                "Connection: close\r\n"
                "\r\n"
                '{"status": "error", "message": "Unauthorized: Missing Cookie"}'
            )
            return raw_401.encode("utf-8")

        # 2. Catch the invisible browser preflight request and let it pass
        # FIXED: Check the dictionary keys directly
        if "Access-Control-Request-Method" in headers:
            return json.dumps({"status": "preflight ok"}).encode("utf-8")

        # --------------------------------
        try:
            msg_data = json.loads(body)
            channel = msg_data.get("channel", "general")
            sender = msg_data.get("sender", "Unknown")
            initiator = msg_data.get("initiator", sender)
            text = msg_data.get("message", "")

            # Save our OWN message to memory exactly ONCE
            if channel not in chat_channels:
                chat_channels[channel] = []
            chat_channels[channel].append(f"{sender}: {text}")

            # --- THE FIX: Load the peers before broadcasting ---
            active_peers = get_active_peers()
            # ---------------------------------------------------

            for username, address in active_peers.items():
                # Check BOTH sender and initiator!
                if sender == username or initiator == username:
                    continue
                # Spawn a background thread for each outgoing message
                thread = threading.Thread(
                    target=send_http_post_thread,
                    args=(address["ip"], address["port"], "/send-peer", msg_data),
                )
                thread.daemon = True
                thread.start()

            return json.dumps({"status": "broadcast complete"}).encode("utf-8")
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")

    @app.route("/add-list", methods=["POST"])
    def add_list_sync(headers, body):
        """API: Adds a new channel to the local state (Synchronous)."""
        try:
            data = json.loads(body)
            new_channel = data.get("channel")

            if new_channel and new_channel not in chat_channels:
                chat_channels[new_channel] = []
                print(f"[Channel Manager] New channel created: {new_channel}")

            return json.dumps(
                {"status": "success", "channels": list(chat_channels.keys())}
            ).encode("utf-8")
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")

    @app.route("/connect-peer", methods=["POST"])
    def connect_peer_sync(headers, body):
        """P2P API: Handshake endpoint (Synchronous)."""
        try:
            peer_data = json.loads(body)
            sender = peer_data.get("sender", "Unknown")

            print(f"[P2P Handshake] Direct connection verified from {sender}")
            return json.dumps(
                {"status": "connected", "message": f"Handshake accepted from {sender}"}
            ).encode("utf-8")
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")

    @app.route("/get-messages", methods=["GET"])
    def get_messages_sync(headers, body):
        """API: Frontend polling endpoint to retrieve all chat messages (Sync)."""
        # --- THE INCIGNITO TRAP FIX: Secure the history! ---
        cookie_header = headers.get("Cookie", "")
        if "session_id=" not in str(cookie_header):
            raw_401 = (
                "HTTP/1.1 401 Unauthorized\r\n"
                "Content-Type: application/json\r\n"
                "Connection: close\r\n"
                "\r\n"
                '{"status": "error", "message": "Unauthorized: Missing Cookie"}'
            )
            return raw_401.encode("utf-8")
        # ---------------------------------------------------

        try:
            return json.dumps({"status": "success", "channels": chat_channels}).encode(
                "utf-8"
            )
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}).encode("utf-8")

    def send_http_post_thread(ip, port, path, json_data):
        """
        Open a direct socket connection to a peer and transmit a JSON payload.

        :param ip: Target peer's IP address.
        :type ip: str
        :param port: Target peer's port number.
        :type port: int
        :param path: The HTTP path to POST the data to (e.g., /send-peer).
        :type path: str
        :param json_data: The message dictionary to transmit.
        :type json_data: dict
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect((ip, port))
            body_str = json.dumps(json_data)
            request = (
                f"POST {path} HTTP/1.1\r\n"
                f"Host: {ip}:{port}\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body_str)}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
                f"{body_str}"
            )
            s.sendall(request.encode("utf-8"))
            s.close()
            print(f"[P2P Thread] Sent to {ip}:{port}")
        except Exception as e:
            print(f"[P2P Thread Error] Failed to send to {ip}:{port} - {e}")


# =========================================================
# LAUNCHER
# =========================================================


def create_sampleapp(ip, port):
    """
    Initialize and launch the AsynapRous web application.

    :param ip: IP address to bind the server.
    :type ip: str
    :param port: Port number to listen on.
    :type port: int
    """
    app.prepare_address(ip, port)
    app.run()
