import contextlib
import datetime
from argparse import Namespace
from pathlib import Path
from typing import Generator, Optional, Union

import alembic.config
from sqlalchemy import create_engine, delete, select, text, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.types import JSON, TEXT, String

from . import types


class Base(DeclarativeBase):
    pass


class Point(Base):
    __tablename__ = "points"
    id: Mapped[int] = mapped_column(primary_key=True)
    time: Mapped[datetime.datetime] = mapped_column()
    metric_name: Mapped[str] = mapped_column(String(255))
    metric_value: Mapped[Optional[float]] = mapped_column()
    absolute_max: Mapped[Optional[float]] = mapped_column()
    absolute_min: Mapped[Optional[float]] = mapped_column()
    relative_max: Mapped[Optional[float]] = mapped_column()
    relative_min: Mapped[Optional[float]] = mapped_column()
    skipped: Mapped[bool] = mapped_column(server_default="0")
    measure_source: Mapped[Optional[str]] = mapped_column(TEXT)
    diffable_content: Mapped[Optional[str]] = mapped_column(TEXT)
    url: Mapped[Optional[str]] = mapped_column()
    epoch: Mapped[int] = mapped_column(server_default="0")
    generation: Mapped[int] = mapped_column(server_default="0")
    tags: Mapped[str] = mapped_column(JSON, server_default="{}")


class DB:
    def __init__(self, db_path: Union[Path, str], verbose: bool = False):
        self.engine = create_engine(f"sqlite:///{db_path}", echo=verbose)
        self.db_path = Path(db_path)
        self._migrated = False

    def add(self, point: types.Point):
        with self.session() as session:
            db_point = Point(
                time=point.time,
                metric_name=point.metric_name,
                metric_value=point.metric_value,
                absolute_max=point.absolute_max,
                absolute_min=point.absolute_min,
                relative_max=point.relative_max,
                relative_min=point.relative_min,
                measure_source=point.measure_source,
                diffable_content=point.diffable_content,
                url=point.url,
                skipped=point.skipped,
                epoch=point.epoch,
                generation=point.generation,
                tags=point.tags,
            )
            session.add(db_point)
            session.commit()
            return types.Point.model_validate(db_point)

    def skip_latest(self, metric_name: str):
        to_update = (
            select(Point.id)
            .filter_by(metric_name=metric_name)
            .order_by(Point.time.desc(), Point.id.desc())
            .limit(1)
        )
        query = (
            update(Point)
            .values(skipped=True)
            .where(Point.id.in_(to_update.scalar_subquery()))
        )
        with self.session() as session:
            session.execute(query)
            session.commit()

    def recent(
        self, metric_name: Optional[str] = None, count: Optional[int] = 10
    ) -> Generator[Point, None, None]:
        query = select(Point)
        if metric_name is not None:
            query = query.filter_by(metric_name=metric_name)
        query = query.order_by(Point.time.desc(), Point.id.desc())
        if count is not None:
            query = query.limit(count)
        with self.session() as session:
            for row in session.execute(query):
                yield row[0]

    def rename(self, old_metric_name: str, new_metric_name: str) -> int:
        query = (
            update(Point)
            .values(metric_name=new_metric_name)
            .where(Point.metric_name == old_metric_name)
        )
        count = 0
        with self.session() as session:
            count = session.execute(query).rowcount
            session.commit()
        return count

    def iter_all(self) -> Generator[Point, None, None]:
        query = select(Point)
        with self.session() as session:
            for row in session.execute(query):
                yield row[0]

    def iter_metric_names(self) -> Generator[str, None, None]:
        with self.session() as session:
            metric_names_query = select(Point.metric_name.distinct())
            for metric_name in session.execute(metric_names_query):
                yield metric_name[0]

    def prune_before(self, point: Point) -> int:
        count = 0
        with self.session() as session:
            count = session.execute(
                delete(Point)
                .where(Point.metric_name == point.metric_name)
                .where(Point.id < point.id)
            ).rowcount
            session.commit()
        return count

    def migrate(self):
        self._ensure_dir()
        self.run_alembic("upgrade", "head")

    def run_alembic(self, *args):
        AlembicCLI(db_url=self.engine.url).main(argv=args)

    def vacuum(self):
        with self.session() as session:
            session.execute(text("VACUUM"))

    @contextlib.contextmanager
    def session(self) -> Generator[Session, None, None]:
        self._ensure_dir()
        if not self._migrated:
            self.migrate()
            self._migrated = True
        with Session(self.engine) as session:
            yield session

    def _ensure_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


class AlembicCLI(alembic.config.CommandLine):
    def __init__(self, db_url: str):
        super().__init__()
        self.db_url = db_url

    def run_cmd(self, config: alembic.config.Config, options: Namespace) -> None:
        config.config_args["libroot"] = Path(__file__).parent
        config.config_args["db_url"] = self.db_url
        config.config_file_name = config.config_args["libroot"] / "alembic.ini"
        return super().run_cmd(config, options)
