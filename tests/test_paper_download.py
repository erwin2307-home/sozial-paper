from unittest.mock import MagicMock, patch

from modules import paper_download

PUBLIC_DNS = [(2, 0, 0, "", ("93.184.216.34", 0))]


def _response(content=b"", redirect_to=None):
    resp = MagicMock()
    resp.content = content
    resp.is_redirect = redirect_to is not None
    resp.headers = {"Location": redirect_to} if redirect_to else {}
    return resp


def test_fetch_pdf_follows_public_redirect():
    responses = [_response(redirect_to="/final.pdf"), _response(content=b"%PDF-data")]
    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS), \
         patch("modules.paper_download.requests.get", side_effect=responses) as mock_get:
        assert paper_download.fetch_pdf("https://example.com/start") == b"%PDF-data"
    assert mock_get.call_args_list[1].args[0] == "https://example.com/final.pdf"


def test_fetch_pdf_blocks_redirect_to_private_address():
    def dns(host, *_args, **_kwargs):
        ip = "169.254.169.254" if host == "metadata.internal" else "93.184.216.34"
        return [(2, 0, 0, "", (ip, 0))]

    with patch("socket.getaddrinfo", side_effect=dns), \
         patch("modules.paper_download.requests.get",
               return_value=_response(redirect_to="http://metadata.internal/x")) as mock_get:
        assert paper_download.fetch_pdf("https://example.com/start") is None
    mock_get.assert_called_once()


def test_fetch_pdf_gives_up_after_too_many_redirects():
    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS), \
         patch("modules.paper_download.requests.get",
               return_value=_response(redirect_to="https://example.com/loop")) as mock_get:
        assert paper_download.fetch_pdf("https://example.com/loop") is None
    assert mock_get.call_count == paper_download.MAX_REDIRECTS + 1


def test_fetch_pdf_returns_none_on_http_error():
    resp = _response()
    resp.raise_for_status.side_effect = RuntimeError("404")
    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS), \
         patch("modules.paper_download.requests.get", return_value=resp):
        assert paper_download.fetch_pdf("https://example.com/x.pdf") is None
