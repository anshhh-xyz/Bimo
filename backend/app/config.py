import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


def dev_tokens() -> dict[str, int]:
    """DEV_TOKENS='tokenA:1,tokenB:2' -> {'tokenA': 1, 'tokenB': 2}.
    Read on every call so tests can change the env var."""
    tokens: dict[str, int] = {}
    for pair in (p.strip() for p in os.environ.get("DEV_TOKENS", "").split(",")):
        if not pair:
            continue
        token, sep, uid = pair.rpartition(":")
        if not sep or not token or not uid.isdigit():
            raise ValueError("DEV_TOKENS must look like 'token:user_id,token:user_id'")
        tokens[token] = int(uid)
    return tokens


def public_url() -> str:
    """Public https base URL of this server (the tunnel URL), no trailing slash."""
    return os.environ.get("PUBLIC_URL", "").rstrip("/")


def user_passphrases() -> dict[str, str]:
    """USER_PASSPHRASES='alice@example.com:phrase1,bob@example.com:phrase2'
    -> {'alice@example.com': 'phrase1', ...}. Used on the OAuth login page."""
    out: dict[str, str] = {}
    for pair in (p.strip() for p in os.environ.get("USER_PASSPHRASES", "").split(",")):
        if not pair:
            continue
        email, sep, phrase = pair.partition(":")
        if not sep or not email or not phrase:
            raise ValueError("USER_PASSPHRASES must look like 'email:passphrase,email:passphrase'")
        out[email.lower()] = phrase
    return out


def allowed_redirect(uri: str) -> bool:
    """Only let OAuth redirect to Claude's own callback hosts, or localhost (Claude Code)."""
    p = urlparse(uri)
    if p.fragment:
        return False
    hosts = {h.strip() for h in
             os.environ.get("ALLOWED_REDIRECT_HOSTS", "claude.ai,claude.com,chatgpt.com").split(",")
             if h.strip()}
    if p.scheme == "https" and p.hostname in hosts:
        return True
    return p.scheme == "http" and p.hostname in {"localhost", "127.0.0.1"}


"""Everything environment-specific lives in one file. 
The redirect allowlist stops an attacker from registering a client that sends login codes to their own site."""