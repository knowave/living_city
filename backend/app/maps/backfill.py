"""Entrypoint: `uv run python -m app.maps.backfill`. Builds maps for worlds that have none."""
from sqlalchemy import select

from app.db.session import SessionLocal
from app.maps.generator import generate_map
from app.maps.validate import MapValidationError, validate_map
from app.models import Building, MapChunk, World
from app.repositories.sqlalchemy import SqlMapChunkRepository
from app.simulation.interfaces import BuildingFootprint


def main() -> None:
    done = skipped = failed = 0
    with SessionLocal() as session:
        repo = SqlMapChunkRepository(session)
        for world_id, seed in session.execute(select(World.id, World.seed).order_by(World.id)).all():
            if repo.count(world_id):
                skipped += 1
                continue
            rows = session.execute(
                select(Building.id, Building.tile_x, Building.tile_y, Building.width, Building.height)
                .where(Building.world_id == world_id)
                .order_by(Building.id)
            ).all()
            footprints = [BuildingFootprint(str(r[0]), *r[1:]) for r in rows]
            game_map = generate_map(seed, footprints)
            try:
                validate_map(game_map, footprints)
            except MapValidationError as exc:
                failed += 1
                print(f"world {world_id}: skipped, {exc.reason}")
                continue
            repo.save_all(world_id, game_map.chunks())
            session.commit()
            done += 1
    print(f"backfill: created={done} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
