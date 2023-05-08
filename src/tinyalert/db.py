import datetime
import contextlib
from argparse import Namespace
from pathlib import Path
from typing import Generator, Optional

import alembic.config

from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session
from sqlalchemy.types import String, TEXT

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
    ignore: Mapped[Optional[types.IgnoreType]] = mapped_column()
    url: Mapped[Optional[str]] = mapped_column()
    diffable_content: Mapped[Optional[str]] = mapped_column(TEXT)


class DB:
    def __init__(self, db_path: Path):
        self.engine = create_engine(
            f"sqlite:///{db_path}", echo=True, isolation_level="READ UNCOMMITTED"
        )
        self.db_path = db_path

    def add(self, point: types.Point):
        with self.session() as session:
            session.add(
                Point(
                    time=point.time,
                    metric_name=point.metric_name,
                    metric_value=point.metric_value,
                    absolute_max=point.absolute_max,
                    absolute_min=point.absolute_min,
                    relative_max=point.relative_max,
                    relative_min=point.relative_min,
                    ignore=point.ignore,
                    diffable_content=point.diffable_content,
                    url=point.url,
                )
            )
            session.commit()
        return point

    def recent(
        self, metric_name: Optional[str] = None, count: int = 10
    ) -> Generator[types.Point, None, None]:
        query = select(Point)
        if metric_name is not None:
            query = query.filter_by(metric_name=metric_name)
        query = query.order_by(Point.time.desc(), Point.id.desc()).limit(count)
        with self.session() as session:
            for row in session.execute(query):
                yield types.Point.model_validate(row[0])

    def iter_all(self) -> Generator[types.Point, None, None]:
        query = select(Point)
        with self.session() as session:
            for row in session.execute(query):
                yield types.Point.model_validate(row[0])

    def iter_metric_names(self) -> Generator[str, None, None]:
        with self.session() as session:
            metric_names_query = select(Point.metric_name.distinct())
            for metric_name in session.execute(metric_names_query):
                yield metric_name[0]

    def prune(self, keep: int = 10) -> int:
        count = 0
        with self.session() as session:
            metric_names_query = select(Point.metric_name.distinct())
            for metric_name in session.execute(metric_names_query):
                to_delete = (
                    select(Point.id)
                    .filter_by(metric_name=metric_name[0])
                    .order_by(Point.time.desc(), Point.id.desc())
                    .offset(keep)
                )
                count += session.execute(
                    delete(Point).where(Point.id.in_(to_delete.scalar_subquery()))
                ).rowcount
                session.commit()
        return count

    def migrate(self):
        self.run_alembic("upgrade", "head")

    def run_alembic(self, *args):
        AlembicCLI(db_url=self.engine.url).main(argv=args)

    @contextlib.contextmanager
    def session(self) -> Generator[Session, None, None]:
        with Session(self.engine) as session:
            yield session


class AlembicCLI(alembic.config.CommandLine):
    def __init__(self, db_url: str):
        super().__init__()
        self.db_url = db_url

    def run_cmd(self, config: alembic.config.Config, options: Namespace) -> None:
        config.config_args["libroot"] = Path(__file__).parent
        config.config_args["db_url"] = self.db_url
        config.config_file_name = config.config_args["libroot"] / "alembic.ini"
        return super().run_cmd(config, options)