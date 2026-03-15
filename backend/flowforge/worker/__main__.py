import asyncio
from flowforge.config import get_settings


async def main():
    settings = get_settings()
    print(f"Worker starting, redis={settings.redis_url}")
    # StreamConsumer will be wired in Task 4


if __name__ == "__main__":
    asyncio.run(main())
