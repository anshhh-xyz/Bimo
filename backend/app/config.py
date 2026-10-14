import os
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

"""dev_tokens() is a helper used by the auth middleware to look up
the user ID for a given token. It reads the DEV_TOKENS environment
variable, which we'll set in .env for local development."""

"""It gives the MCP layer a way to know which user is calling before real OAuth (3.5) exists. 
Each token maps to one user, which is how your three accounts become three identities"""