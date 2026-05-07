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

from urllib.parse import urlparse, unquote


def get_auth_from_url(url):
    """Given a url with authentication components, extract them into a tuple of
    username,password.

    :rtype: (str,str)
    """
    parsed = urlparse(url)

    try:
        auth = (unquote(parsed.username), unquote(parsed.password))
    except (AttributeError, TypeError):
        auth = ("", "")

    return auth


def get_encoding_from_headers(headers):
    """
    Given a dictionary of HTTP headers, extract the character encoding.
    Defaults to 'utf-8' if none is found.

    :rtype: str
    """
    # Header keys are often case-insensitive, but let's assume CaseInsensitiveDict is used
    content_type = headers.get("Content-Type", "") or headers.get("content-type", "")

    if "charset=" in content_type:
        # Extract the value right after 'charset='
        return content_type.split("charset=")[-1].split(";")[0].strip()

    return "utf-8"
