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
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict
from .utils import get_auth_from_url, get_encoding_from_headers

import base64  # added
import asyncio
import inspect


class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>`
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        """
        Initialize a new HttpAdapter instance.

        :param ip: IP address of the client.
        :type ip: str
        :param port: Port number of the client.
        :type port: int
        :param conn: Active socket connection.
        :type conn: socket.socket
        :param connaddr: Address of the connected client.
        :type connaddr: tuple
        :param routes: Mapping of route paths to handler functions.
        :type routes: dict
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn: The client socket connection.
        :type conn: socket.socket
        :param addr: The client's address tuple (IP, port).
        :type addr: tuple
        :param routes: The route mapping for dispatching requests.
        :type routes: dict
        """
        self.conn = conn
        self.connaddr = addr
        req = self.request
        resp = self.response

        print("[HttpAdapter] Invoke handle_client connection {}".format(addr))

        # --- THE FIX: ROBUST SOCKET READING ---
        raw_request = b""

        # 1. Read until the end of the HTTP headers (\r\n\r\n)
        while b"\r\n\r\n" not in raw_request:
            try:
                chunk = conn.recv(1024)
                if not chunk:
                    break  # Client disconnected
                raw_request += chunk
            except BlockingIOError:
                continue  # Ignore non-blocking wait
            except Exception as e:
                print(f"[HttpAdapter] Read error: {e}")
                break

        if not raw_request:
            conn.close()
            return

        header_data, separator, body_data = raw_request.partition(b"\r\n\r\n")

        # 2. Find the Content-Length
        content_length = 0
        header_text = header_data.decode("utf-8", errors="ignore")
        for line in header_text.split("\r\n"):
            if line.lower().startswith("content-length:"):
                try:
                    content_length = int(line.split(":")[1].strip())
                except ValueError:
                    pass

        # 3. Read the remaining body based on Content-Length
        while len(body_data) < content_length:
            try:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                body_data += chunk
            except BlockingIOError:
                continue

        msg = (header_data + separator + body_data).decode("utf-8", errors="ignore")
        req.prepare(msg, routes)
        # --------------------------------------

        # Handle request hook
        if req.hook:
            if inspect.iscoroutinefunction(req.hook):
                hook_result = asyncio.run(req.hook(headers=req.headers, body=req.body))
            else:
                hook_result = req.hook(headers=req.headers, body=req.body)

            if isinstance(hook_result, str):
                hook_result = hook_result.encode("utf-8")

            if hook_result.startswith(b"HTTP/"):
                response = hook_result
            else:
                header = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(hook_result)}\r\n"
                    "Connection: close\r\n"
                    "Access-Control-Allow-Origin: *\r\n"
                    "Access-Control-Allow-Headers: *\r\n"
                    "Access-Control-Allow-Methods: *\r\n"
                    "\r\n"
                ).encode("utf-8")
                response = header + hook_result
        else:
            response = resp.build_response(req)

        conn.sendall(response)
        conn.close()

    async def handle_client_coroutine(self, reader, writer):
        """
        Handle an incoming client connection using stream reader writer asynchronously.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param reader: The asyncio stream reader.
        :type reader: asyncio.StreamReader
        :param writer: The asyncio stream writer.
        :type writer: asyncio.StreamWriter
        """
        req = self.request
        resp = self.response
        addr = writer.get_extra_info("peername")
        print("[HttpAdapter] Invoke handle_client_coroutine connection {}".format(addr))

        # --- THE FIX: ROBUST ASYNC READING ---
        raw_request = b""

        # 1. Read until end of headers
        while b"\r\n\r\n" not in raw_request:
            chunk = await reader.read(1024)
            if not chunk:
                break
            raw_request += chunk

        if not raw_request:
            writer.close()
            return

        header_data, separator, body_data = raw_request.partition(b"\r\n\r\n")

        # 2. Find Content-Length
        content_length = 0
        header_text = header_data.decode("utf-8", errors="ignore")
        for line in header_text.split("\r\n"):
            if line.lower().startswith("content-length:"):
                try:
                    content_length = int(line.split(":")[1].strip())
                except ValueError:
                    pass

        # 3. Read exact remaining body length
        while len(body_data) < content_length:
            chunk = await reader.read(4096)
            if not chunk:
                break
            body_data += chunk

        msg = (header_data + separator + body_data).decode("utf-8", errors="ignore")
        req.prepare(msg, routes=self.routes)
        # --------------------------------------

        # Handle request hook
        if req.hook:
            if inspect.iscoroutinefunction(req.hook):
                hook_result = await req.hook(
                    headers=req.headers, body=req.body
                )  # Use await directly instead of asyncio.run
            else:
                hook_result = req.hook(headers=req.headers, body=req.body)

            if isinstance(hook_result, str):
                hook_result = hook_result.encode("utf-8")

            if hook_result.startswith(b"HTTP/"):
                response = hook_result
            else:
                header = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(hook_result)}\r\n"
                    "Connection: close\r\n"
                    "Access-Control-Allow-Origin: *\r\n"
                    "Access-Control-Allow-Headers: *\r\n"
                    "Access-Control-Allow-Methods: *\r\n"
                    "\r\n"
                ).encode("utf-8")
                response = header + hook_result
        else:
            response = resp.build_response(req)

        # In async, we write to the writer stream
        writer.write(response)
        await writer.drain()
        writer.close()

    def extract_cookies(self, req, resp):
        """
        Build cookies from the :class:`Request <Request>` headers.

        :param req:(Request) The :class:`Request <Request>` object.
        :param resp: (Response) The res:class:`Response <Response>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
        cookies = {}
        if "Cookie" in req.headers:
            cookie_str = req.headers["Cookie"]
            for pair in cookie_str.split(";"):
                if "=" in pair:
                    key, value = pair.strip().split("=", 1)
                    cookies[key] = value
        return cookies

    def build_response(self, req, resp):
        """Builds a :class:`Response <Response>` object

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response()

        # Set encoding.
        response.encoding = get_encoding_from_headers(response.headers)
        response.raw = resp
        response.reason = getattr(resp, "reason", "OK")

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Add new cookies from the server.
        response.cookies = self.extract_cookies(req, resp)

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response

    def build_json_response(self, req, resp):
        """Builds a :class:`Response <Response>` object from JSON data

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response(req)

        # Set encoding.
        response.raw = resp

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response

    # def get_connection(self, url, proxies=None):
    # """Returns a url connection for the given URL.

    # :param url: The URL to connect to.
    # :param proxies: (optional) A Requests-style dictionary of proxies used on this request.
    # :rtype: int
    # """

    # proxy = select_proxy(url, proxies)

    # if proxy:
    # proxy = prepend_scheme_if_needed(proxy, "http")
    # proxy_url = parse_url(proxy)
    # if not proxy_url.host:
    # raise InvalidProxyURL(
    # "Please check proxy URL. It is malformed "
    # "and could be missing the host."
    # )
    # proxy_manager = self.proxy_manager_for(proxy)
    # conn = proxy_manager.connection_from_url(url)
    # else:
    # # Only scheme should be lower case
    # parsed = urlparse(url)
    # url = parsed.geturl()
    # conn = self.poolmanager.connection_from_url(url)

    # return conn

    def add_headers(self, request):
        """
        Add headers to the request.

        This method is intended to be overridden by subclasses to inject
        custom headers. It does nothing by default.


        :param request: :class:`Request <Request>` to add headers to.
        """
        pass

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy.

        :class:`HttpAdapter <HttpAdapter>`.

        :param proxy: The url of the proxy being used for this request.
        :rtype: dict
        """
        headers = {}
        #
        # TODO: build your authentication here
        #       username, password =...
        # we provide dummy auth here
        #

        ## username, password = ("user1", "password")

        username, password = get_auth_from_url(proxy)

        """
        if username:
            headers["Proxy-Authorization"] = (username, password)
        """

        # Encode both username and password by concatination (salting) and then base64 encoding
        if username and password:
            auth_string = f"{username}:{password}"
            b64_auth_string = base64.b64encode(auth_string.encode("utf-8")).decode(
                "utf-8"
            )
            headers["Proxy-Authorization"] = f"Basic {b64_auth_string}"

        return headers
