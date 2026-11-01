import ipaddress
import socket
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

MAX_REDIRECTS = 5


def is_safe_url(url: str) -> bool:
    """Reject URLs that resolve to private/loopback/link-local/reserved IPs.

    Prevents SSRF via a malicious pdf_url returned by a third-party search
    API (e.g. a cloud metadata endpoint or an internal service address).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        for info in socket.getaddrinfo(parsed.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except Exception:
        return False


def fetch_pdf(url: str) -> Optional[bytes]:
    """Download a PDF, validating every redirect hop against is_safe_url."""
    try:
        for _ in range(MAX_REDIRECTS + 1):
            if not is_safe_url(url):
                return None
            response = requests.get(url, timeout=30, allow_redirects=False)
            if not response.is_redirect:
                response.raise_for_status()
                return response.content
            url = urljoin(url, response.headers["Location"])
    except Exception:
        return None
    return None
