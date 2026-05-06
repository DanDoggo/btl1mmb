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
daemon.backend
~~~~~~~~~~~~~~~~~

This module provides a backend object to manage and persist backend daemon. 
It implements a basic backend server using Python's socket and threading libraries.
It supports handling multiple client connections concurrently and routing requests using a
custom HTTP adapter.

Requirements:
--------------
- socket: provide socket networking interface.
- threading: Enables concurrent client handling via threads.
- response: response utilities.
- httpadapter: the class for handling HTTP requests.
- CaseInsensitiveDict: provides dictionary for managing headers or routes.


Notes:
------
- The server create daemon threads for client handling.
- The current implementation error handling is minimal, socket errors are printed to the console.
- The actual request processing is delegated to the HttpAdapter class.

Usage Example:
--------------
>>> create_backend("127.0.0.1", 9000, routes={})

"""

import socket
import threading
import argparse
import asyncio
import inspect
import selectors

from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

sel = selectors.DefaultSelector()

# =========================================================
# THE NON-BLOCKING TOGGLE SWITCH
# =========================================================
# Make sure P2P_MODE in apps/sampleapp.py matches this setting!
mode_async = "coroutine" 
# mode_async = "threading"
# mode_async = "callback"

def handle_client(ip, port, conn, addr, routes):
    print("[Backend] Invoke handle_client accepted connection from {}".format(addr))
    daemon = HttpAdapter(ip, port, conn, addr, routes)
    daemon.handle_client(conn, addr, routes)

def handle_client_callback(server, ip, port,conn, addr, routes):
    print("[Backend] Invoke handle_client_callback accepted connection from {}".format(addr))
    daemon = HttpAdapter(ip, port, conn, addr, routes)
    daemon.handle_client(conn, addr, routes)

async def async_server(ip="0.0.0.0", port=7000, routes={}):
    print("[Backend] async_server **ASYNC** listening on port {}".format(port))
    if routes != {}:
        print("[Backend] route settings")
        for key, value in routes.items():
            isCoFunc = ""
            if inspect.iscoroutinefunction(value):
               isCoFunc += "**ASYNC** "
            print("   + ('{}', '{}'): {}{}".format(key[0], key[1], isCoFunc, str(value)))
    
    async def handle_client_wrapper(reader, writer):
        addr = writer.get_extra_info("peername")
        print("[Backend] Invoke handle_client_wrapper accepted connection from {}".format(addr))
        daemon = HttpAdapter(ip, port, None, addr, routes)
        await daemon.handle_client_coroutine(reader, writer)
        writer.close()

    server = await asyncio.start_server(handle_client_wrapper, ip, port)
    async with server:
        await server.serve_forever()
    return

def run_backend(ip, port, routes):
    global mode_async
    print("[Backend] run_backend with routes={}".format(routes))
    
    if mode_async == "coroutine":
       asyncio.run(async_server(ip, port, routes))
       return

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind((ip, port))
        server.listen(50)

        print("[Backend] Listening on port {} (Mode: {})".format(port, mode_async))
        if routes != {}:
            print("[Backend] route settings")
            for key, value in routes.items():
               isCoFunc = ""
               if inspect.iscoroutinefunction(value):
                  isCoFunc += "**ASYNC** "
               print("   + ('{}', '{}'): {}{}".format(key[0], key[1], isCoFunc, str(value)))

        if mode_async == "callback":
            server.setblocking(False) # MUST be non-blocking before the loop
            sel.register(server, selectors.EVENT_READ, data=("accept", ip, port, routes))

            print("[Backend] Entering Selector Event Loop")
            while True:
                events = sel.select(timeout=None)
                for key, mask in events:
                    action_type = key.data[0]
                    
                    if action_type == "accept":
                        # The server socket is ready to accept a new client
                        conn, addr = server.accept()
                        conn.setblocking(False)
                        # Register the NEW client socket to listen for incoming data
                        sel.register(conn, selectors.EVENT_READ, data=("read", addr, key.data[3]))
                        
                    elif action_type == "read":
                        # A client socket sent data
                        client_conn = key.fileobj
                        client_addr = key.data[1]
                        client_routes = key.data[2]
                        
                        # Unregister so we don't trigger multiple times
                        sel.unregister(client_conn) 
                        
                        # Pass to your adapter!
                        handle_client_callback(server, ip, port, client_conn, client_addr, client_routes)

        else:
            # ORIGINAL THREADING MODE (Works perfectly)
            while True:
                conn, addr = server.accept()
                client_thread = threading.Thread(target=handle_client, args=(ip, port, conn, addr, routes))
                client_thread.daemon = True
                client_thread.start()

    except socket.error as e:
      print("Socket error: {}".format(e))

def create_backend(ip, port, routes={}):
    run_backend(ip, port, routes)
