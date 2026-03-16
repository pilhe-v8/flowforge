import asyncio
import time

from aiohttp import web

from flowforge.config import get_settings
from flowforge.worker.consumer import StreamConsumer

consumer: StreamConsumer | None = None


async def health_handler(request):
    return web.json_response(
        {
            "status": "healthy",
            "consumer_id": consumer.consumer_id if consumer else "not started",
            "messages_processed": consumer.message_count if consumer else 0,
            "last_processed_ago_seconds": (
                time.monotonic() - consumer.last_processed_at if consumer else None
            ),
        }
    )


async def start_health_server(port: int):
    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


async def main():
    global consumer
    settings = get_settings()
    health_port = int(getattr(settings, "health_port", 8081))
    await start_health_server(health_port)
    consumer = StreamConsumer(settings)
    await consumer.consume()


if __name__ == "__main__":
    asyncio.run(main())
