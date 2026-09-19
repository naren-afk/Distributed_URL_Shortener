import asyncio
from datetime import datetime
import json
import logging
import signal
from typing import Any, Dict, List
import redis.asyncio as aioredis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.analytics import ClickEvent
from app.models.url import URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("AnalyticsWorker")


class AnalyticsWorker:
    def __init__(self, session_factory=None):
        self.running = True
        self.redis: aioredis.Redis | None = None
        self.session_factory = session_factory or AsyncSessionLocal

    async def setup(self):
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        logger.info(f"Analytics Worker connected to Redis at {settings.REDIS_URL}")

    async def teardown(self):
        if self.redis:
            await self.redis.aclose()
            logger.info("Analytics Worker Redis connection closed.")

    async def process_batch(self, events: List[Dict[str, Any]]):
        """Bulk insert click events and update click counts in a single DB transaction."""
        if not events:
            return

        async with self.session_factory() as session:
            try:
                click_models = []
                code_counts: Dict[str, int] = {}

                for ev in events:
                    # Parse timestamp
                    ts_str = ev.get("timestamp")
                    ts = datetime.fromisoformat(ts_str) if ts_str else datetime.utcnow()

                    click = ClickEvent(
                        short_code=ev.get("short_code"),
                        timestamp=ts,
                        ip_address=ev.get("ip_address"),
                        referrer=ev.get("referrer"),
                        user_agent=ev.get("user_agent"),
                        browser=ev.get("browser"),
                        os=ev.get("os"),
                        country=ev.get("country"),
                    )
                    click_models.append(click)

                    code = ev.get("short_code")
                    if code:
                        code_counts[code] = code_counts.get(code, 0) + 1

                # Bulk insert click logs
                session.add_all(click_models)

                # Batch update URL click counters
                for code, increment in code_counts.items():
                    stmt = (
                        update(URL)
                        .where(URL.short_code == code)
                        .values(click_count=URL.click_count + increment)
                    )
                    await session.execute(stmt)

                await session.commit()
                logger.info(f"Successfully flushed batch of {len(events)} click events to PostgreSQL.")
            except Exception as e:
                await session.rollback()
                logger.error(f"Error persisting batch of {len(events)} click events: {e}", exc_info=True)

    async def run(self):
        await self.setup()
        logger.info(
            f"Analytics worker started. Polling queue '{settings.CLICK_STREAM_KEY}' "
            f"(batch_size={settings.WORKER_BATCH_SIZE}, interval={settings.WORKER_POLL_INTERVAL}s)..."
        )

        while self.running:
            try:
                # Atomically pop a batch of items from Redis list
                # rpop with count is supported in Redis >= 6.2
                raw_items = await self.redis.rpop(settings.CLICK_STREAM_KEY, count=settings.WORKER_BATCH_SIZE)

                if raw_items:
                    # Ensure raw_items is a list even if a single string is returned
                    if isinstance(raw_items, str):
                        raw_items = [raw_items]

                    parsed_events = []
                    for item in raw_items:
                        try:
                            parsed_events.append(json.loads(item))
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in click event queue: {item}")

                    if parsed_events:
                        await self.process_batch(parsed_events)
                else:
                    # Queue is empty, sleep for poll interval
                    await asyncio.sleep(settings.WORKER_POLL_INTERVAL)

            except asyncio.CancelledError:
                logger.info("Worker received cancellation signal.")
                break
            except Exception as e:
                logger.error(f"Unexpected worker loop error: {e}", exc_info=True)
                await asyncio.sleep(2.0)

        await self.teardown()

    def stop(self):
        self.running = False


async def main():
    worker = AnalyticsWorker()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:
            # Signal handling on Windows event loop may not support add_signal_handler
            pass

    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, stopping worker...")
        worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
