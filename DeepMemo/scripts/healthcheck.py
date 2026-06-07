"""Project health checks for local/dev environments."""

from __future__ import annotations

from tools.utils.config import API_KEY, CACHE_FILE, DATABASE_FILE, get_config_summary
from tools.utils.database import create_tables
from tools.utils.question_cache import get_cache_count


def main() -> int:
    create_tables()
    summary = get_config_summary()

    print("[health] project config loaded")
    print(f"[health] db_file={DATABASE_FILE}")
    print(f"[health] cache_file={CACHE_FILE}")
    print(f"[health] cache_items={get_cache_count()}")
    print(f"[health] api_key_set={bool(API_KEY)}")
    print(f"[health] mode={summary['environment']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

