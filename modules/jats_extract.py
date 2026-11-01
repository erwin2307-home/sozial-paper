from defusedxml import ElementTree as ET


def is_jats_xml(content) -> bool:
    return isinstance(content, bytes) and content.lstrip().startswith(b"<")


def _collect_blocks(node, blocks: list) -> None:
    for child in node:
        if child.tag in ("title", "p"):
            text = " ".join("".join(child.itertext()).split())
            if text:
                blocks.append(text)
        else:
            _collect_blocks(child, blocks)


def extract_text(xml_bytes: bytes) -> tuple:
    """Read the article body from JATS XML; an HTML page or empty body counts as failed."""
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return "", "failed"
    body = root.find("body") if root.tag == "article" else None
    if body is None:
        return "", "failed"
    blocks = []
    _collect_blocks(body, blocks)
    if not blocks:
        return "", "failed"
    return "\n\n".join(blocks), "ok"
