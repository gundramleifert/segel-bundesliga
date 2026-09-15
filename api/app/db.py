from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

if engine.dialect.name == "sqlite":

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(connection, _record) -> None:
        """WAL and a busy timeout — the storage decision of Story L-1.

        SQLite's default journal takes an exclusive lock for every commit, and tracking
        commits a batch of fixes every few seconds per boat; without this, the race
        committee's result PUT and every spectator's GET would queue behind the phones.
        WAL lets readers read while a writer writes, and the timeout makes two writers wait
        instead of failing with "database is locked".
        """
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
