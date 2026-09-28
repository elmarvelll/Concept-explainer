import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

# Same database the Next.js app's Prisma schema owns (frontend/prisma/schema.prisma)
# — that's the source of truth for the schema and its migrations. This
# service only reads and writes rows through the existing tables, it never
# creates or alters them, so there's no migration tooling here.
#
# DATABASE_URL is a standard `mysql://...` connection string (the same
# format Prisma uses); SQLAlchemy's asyncmy dialect needs the
# `mysql+asyncmy://` scheme instead, so swap it in rather than requiring two
# near-identical env vars.
_raw_url = os.environ["DATABASE_URL"]
_ASYNC_URL = _raw_url.replace("mysql://", "mysql+asyncmy://", 1)

engine = create_async_engine(_ASYNC_URL, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
