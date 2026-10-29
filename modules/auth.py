import hmac


def check_password(entered: str, secret: str) -> bool:
    return bool(entered) and hmac.compare_digest(entered.encode(), secret.encode())
