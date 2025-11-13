# Script: app/scripts/dedupe_db.py
# Purpose: Clean duplicate Hotels and Rooms in Postgres, reassign FKs, and optionally add unique indexes.

import asyncio
import argparse
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal


HOTEL_PREVIEW_SQL = text(
    """
    SELECT lower(name) AS name, lower(city) AS city, COUNT(*) AS cnt, array_agg(id ORDER BY id) AS ids
    FROM hotels
    GROUP BY lower(name), lower(city)
    HAVING COUNT(*) > 1
    ORDER BY 1,2;
    """
)

ROOM_PREVIEW_SQL = text(
    """
    SELECT hotel_id, lower(room_type) AS room_type, price, COUNT(*) AS cnt, array_agg(id ORDER BY id) AS ids
    FROM rooms
    GROUP BY hotel_id, lower(room_type), price
    HAVING COUNT(*) > 1
    ORDER BY 1,2,3;
    """
)

FIX_HOTELS_SQL = text(
    """
    WITH hotel_groups AS (
      SELECT id, name, city,
             MIN(id) OVER (PARTITION BY lower(name), lower(city)) AS canonical_id
      FROM hotels
    ),
    dupes AS (
      SELECT id, canonical_id FROM hotel_groups WHERE id <> canonical_id
    )
    UPDATE rooms r
    SET hotel_id = d.canonical_id
    FROM dupes d
    WHERE r.hotel_id = d.id;
    """
)

FIX_BOOKINGS_HOTEL_FK_SQL = text(
    """
    WITH hotel_groups AS (
      SELECT id, name, city,
             MIN(id) OVER (PARTITION BY lower(name), lower(city)) AS canonical_id
      FROM hotels
    ),
    dupes AS (
      SELECT id, canonical_id FROM hotel_groups WHERE id <> canonical_id
    )
    UPDATE bookings b
    SET hotel_id = d.canonical_id
    FROM dupes d
    WHERE b.hotel_id = d.id;
    """
)

DELETE_DUP_HOTELS_SQL = text(
    """
    WITH hotel_groups AS (
      SELECT id, name, city,
             MIN(id) OVER (PARTITION BY lower(name), lower(city)) AS canonical_id
      FROM hotels
    ),
    dupes AS (
      SELECT id FROM hotel_groups WHERE id <> canonical_id
    )
    DELETE FROM hotels h
    USING dupes d
    WHERE h.id = d.id;
    """
)

FIX_ROOMS_SQL = text(
    """
    WITH room_groups AS (
      SELECT id, hotel_id, room_type, price,
             MIN(id) OVER (PARTITION BY hotel_id, lower(room_type), price) AS canonical_id
      FROM rooms
    ),
    dupes AS (
      SELECT id, canonical_id FROM room_groups WHERE id <> canonical_id
    )
    UPDATE bookings b
    SET room_id = d.canonical_id
    FROM dupes d
    WHERE b.room_id = d.id;
    """
)

DELETE_DUP_ROOMS_SQL = text(
    """
    WITH room_groups AS (
      SELECT id, hotel_id, room_type, price,
             MIN(id) OVER (PARTITION BY hotel_id, lower(room_type), price) AS canonical_id
      FROM rooms
    ),
    dupes AS (
      SELECT id FROM room_groups WHERE id <> canonical_id
    )
    DELETE FROM rooms r
    USING dupes d
    WHERE r.id = d.id;
    """
)

ADD_INDEXES_SQL = [
    text("CREATE UNIQUE INDEX IF NOT EXISTS ux_hotels_name_city_ci ON hotels (lower(name), lower(city));"),
    text("CREATE UNIQUE INDEX IF NOT EXISTS ux_rooms_hotel_type_price ON rooms (hotel_id, lower(room_type), price);"),
]


async def preview(session: AsyncSession) -> None:
    print("-- Duplicate hotels (by lower(name), lower(city)) --")
    res = await session.execute(HOTEL_PREVIEW_SQL)
    rows = res.fetchall()
    if not rows:
        print("None")
    else:
        for name, city, cnt, ids in rows:
            print(f"{name}, {city} -> {cnt} duplicates: {list(ids)}")

    print("\n-- Duplicate rooms (by (hotel_id, lower(room_type), price)) --")
    res = await session.execute(ROOM_PREVIEW_SQL)
    rows = res.fetchall()
    if not rows:
        print("None")
    else:
        for hotel_id, room_type, price, cnt, ids in rows:
            print(f"hotel {hotel_id}, {room_type}, {price} -> {cnt} duplicates: {list(ids)}")


async def fix(session: AsyncSession, apply_indexes: bool = False) -> None:
    # Wrap in a transaction
    async with session.begin():
        # Repoint FKs then delete dup hotels
        await session.execute(FIX_HOTELS_SQL)
        # If bookings table lacks hotel_id this will be a no-op
        await session.execute(FIX_BOOKINGS_HOTEL_FK_SQL)
        await session.execute(DELETE_DUP_HOTELS_SQL)

        # Repoint bookings.room_id then delete dup rooms
        await session.execute(FIX_ROOMS_SQL)
        await session.execute(DELETE_DUP_ROOMS_SQL)

    if apply_indexes:
        for stmt in ADD_INDEXES_SQL:
            try:
                await session.execute(stmt)
            except Exception as e:
                # Log and continue; index might already exist or fail due to locks
                print(f"Index creation note: {e}")
        await session.commit()


async def main(dry_run: bool, apply_indexes: bool) -> None:
    async with AsyncSessionLocal() as session:
        if dry_run:
            await preview(session)
        else:
            print("Running deduplication...")
            await fix(session, apply_indexes=apply_indexes)
            print("Done. Preview after fix:")
            await preview(session)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deduplicate Hotels and Rooms; repoint FKs; add indexes optionally.")
    parser.add_argument("--dry-run", action="store_true", help="Only list duplicates; no changes applied")
    parser.add_argument("--apply-indexes", action="store_true", help="Add unique indexes after cleanup")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, apply_indexes=args.apply_indexes))
