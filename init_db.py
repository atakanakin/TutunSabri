from __future__ import annotations

import asyncio

from core.database import init_database


def main() -> None:
    asyncio.run(init_database())


if __name__ == "__main__":
    main()
