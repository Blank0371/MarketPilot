"""MarketPilot backend package.

Importing any backend module loads local development configuration from a
repo-root `.env` file when present. Environment variables already set by the
shell/deployment keep precedence.
"""

from dotenv import load_dotenv

load_dotenv()
