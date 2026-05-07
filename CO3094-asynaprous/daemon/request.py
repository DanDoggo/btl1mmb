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
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist
request settings (cookies, auth, proxies).
"""

from .dictionary import CaseInsensitiveDict

import json  # added
import base64  # added


class Request:
    """The fully mutable "class" `Request <Request>` object,
    containing the exact bytes that will be sent to the server.

    Instances are generated from a "class" `Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    Usage::

      >>> import deamon.request
      >>> req = request.Request()
      ## Incoming message obtain aka. incoming_msg
      >>> r = req.prepare(incoming_msg)
      >>> r
      <Request>
    """

    __attrs__ = [
        "method",
        "url",
        "headers",
        "body",
        "_raw_headers",
        "_raw_body",
        "reason",
        "cookies",
        "body",
        "routes",
        "hook",
    ]

    def __init__(self):
        """Initialize a new Request instance."""
        #: HTTP verb to send to the server.
        self.method = None
        #: HTTP URL to send the request to.
        self.url = None
        #: dictionary of HTTP headers.
        self.headers = None
        #: HTTP path
        self.path = None
        # The cookies set used to create Cookie header
        self.cookies = {}
        #: request body to send to the server.
        self.body = None
        # The raw header
        self._raw_headers = None
        #: The raw body
        self._raw_body = None
        #: Routes
        self.routes = {}
        #: Hook point for routed mapped-path
        self.hook = None

    def extract_request_line(self, request):
        """
        Extract the HTTP method, path, and version from the request line.

        :param request: The raw HTTP request string.
        :type request: str
        :return: A tuple containing (method, path, version).
        :rtype: tuple
        """
        try:
            lines = request.splitlines()
            first_line = lines[0]
            method, path, version = first_line.split()

            if path == "/":
                path = "/login.html"
        except Exception:
            return None, None, None

        return method, path, version

    def prepare_headers(self, raw_request):
        """
        Prepare the given HTTP headers into a CaseInsensitiveDict.

        :param raw_request: The raw HTTP header string.
        :type raw_request: str
        :return: A dictionary of parsed headers.
        :rtype: CaseInsensitiveDict
        """
        lines = raw_request.split("\r\n")
        headers = CaseInsensitiveDict()
        for line in lines[1:]:
            if ": " in line:
                key, val = line.split(": ", 1)
                headers[key] = val
        return headers

    def fetch_headers_body(self, request):
        """
        Split the raw HTTP request into its header and body sections.

        :param request: The raw HTTP request string.
        :type request: str
        :return: A tuple containing the headers and the body.
        :rtype: tuple
        """
        parts = request.split("\r\n\r\n", 1)  # split once at blank line

        _headers = parts[0]
        _body = parts[1] if len(parts) > 1 else ""
        return _headers, _body

    def prepare(self, request, routes=None):
        """
        Prepare the entire request with the given parameters.

        :param request: The raw HTTP request string.
        :type request: str
        :param routes: The routing dictionary. Defaults to None.
        :type routes: dict
        """
        print("[Request] prepare request missg {}".format(request))
        self.method, self.path, self.version = self.extract_request_line(request)
        print(
            "[Request] {} path {} version {}".format(
                self.method, self.path, self.version
            )
        )

        raw_header, raw_body = self.fetch_headers_body(request)
        self._raw_headers = raw_header
        self._raw_body = raw_body
        self.headers = self.prepare_headers(self._raw_headers)
        #
        # @bksysnet Preapring the webapp hook with AsynapRous instance
        # The default behaviour with HTTP server is empty routed
        #
        # TODO manage the webapp hook in this mounting point
        #

        if not routes == {}:
            self.routes = routes
            print("[Request] Routing METHOD {} path {}".format(self.method, self.path))

            routing_path = self.path
            # Remove query parameters (what comes after '?')
            if "?" in routing_path:
                routing_path = routing_path.split("?")[0]
            # Remove trailing slash if it's not the root path
            if routing_path != "/" and routing_path.endswith("/"):
                routing_path = routing_path.rstrip("/")

            # Initial code used self.hook = routes.get((self.method, self.path))
            # But we need to consider the routing path without query parameters and trailing slash
            self.hook = routes.get((self.method, routing_path))
            print("[Request] Hook has request {}".format(request))
            #
            # self.hook manipulation goes here
            # ...
            if self.hook:
                print(
                    "[Request] Hook found for METHOD {} path {}".format(
                        self.method, self.path
                    )
                )
            else:
                print(
                    "[Request] No hook found for METHOD {} path {}".format(
                        self.method, self.path
                    )
                )

        # self._raw_heaers = ""
        # self._raw_body =  ""
        if self._raw_body:
            self.prepare_body(data=self._raw_body, files=None, json_data=None)

        auth_header = self.headers.get("Authorization")
        if auth_header and auth_header.startswith("Basic "):
            b64_auth_string = auth_header.split(" ", 1)[1]
            auth_string = base64.b64decode(b64_auth_string).decode("utf-8")
            username, password = auth_string.split(":", 1)
            self.prepare_auth((username, password))

        cookie_header = None
        for key in self.headers:
            if key.lower() == "cookie":
                cookie_header = self.headers[key]
                break

        if cookie_header:
            for cookie in cookie_header.split(";"):
                if "=" in cookie:
                    key, value = cookie.strip().split("=", 1)
                    self.cookies[key] = value

        return

    def prepare_body(self, data, files, json_data=None):
        """
        Prepare the body of the HTTP request and set Content-Type if JSON.

        :param data: Raw string data for the body.
        :type data: str
        :param files: File data (unused in current implementation).
        :type files: dict
        :param json_data: JSON dictionary to serialize into the body.
        :type json_data: dict
        """
        # self.prepare_content_length(self.body)
        # self.body = body
        #
        # TODO prepare the request authentication
        #
        # self.auth = ...
        if json_data is not None:
            self.body = json.dumps(json_data)
            self.headers["Content-Type"] = "application/json"
        elif data:
            self.body = data
        else:
            self.body = ""

        self.prepare_content_length(self.body)
        return

    def prepare_content_length(self, body):
        """
        Calculate and set the Content-Length header based on the body size.

        :param body: The request body string or bytes.
        :type body: str or bytes
        """
        # self.headers["Content-Length"] = "0"
        #
        # TODO prepare the request authentication
        #
        # self.auth = ...
        if body:
            if isinstance(body, str):
                body_length = len(body.encode("utf-8"))
            else:
                body_length = len(body)
            self.headers["Content-Length"] = str(body_length)
        else:
            self.headers["Content-Length"] = "0"
        return

    def prepare_auth(self, auth, url=""):
        """
        Prepare the Authorization header using Basic Authentication.

        :param auth: A tuple of (username, password).
        :type auth: tuple
        :param url: The URL for authentication (unused).
        :type url: str
        """
        #
        # TODO prepare the request authentication
        #
        # self.auth = ...
        if auth:
            self.auth = auth
            username, password = auth

            auth_string = f"{username}:{password}"
            b64_auth_string = base64.b64encode(auth_string.encode("utf-8")).decode(
                "utf-8"
            )
            self.headers["Authorization"] = f"Basic {b64_auth_string}"
        return

    def prepare_cookies(self, cookies):
        """
        Set the Cookie header for the request.

        :param cookies: The formatted cookie string.
        :type cookies: str
        """
        self.headers["Cookie"] = cookies
