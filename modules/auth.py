def check_password(entered: str, secret: str) -> bool:
    return bool(entered) and entered == secret
