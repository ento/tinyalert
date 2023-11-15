from typing import Optional

import click
import pytimeparse2
from datetime import timedelta


class Duration(click.ParamType):
    name = "duration"

    def convert(self, value, param, ctx):
        if isinstance(value, timedelta):
            return value
        if isinstance(value, (float, int)):
            return timedelta(seconds=value)
        delta = self.from_string(value)
        if delta is None:
            self.fail(f"Invalid duration: {value!r}", param, ctx)
        else:
            return delta

    @staticmethod
    def from_string(value: str) -> Optional[timedelta]:
        secs = pytimeparse2.parse(value)
        return timedelta(seconds=secs) if secs is not None else None
