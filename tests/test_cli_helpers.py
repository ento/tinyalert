from datetime import timedelta

import click
import pytest

from tinyalert.cli_helpers import Duration


@pytest.mark.parametrize(
    "param_type,value,expected",
    [
        (Duration(), timedelta(seconds=1), timedelta(seconds=1)),
        (Duration(), 1, timedelta(seconds=1)),
        (Duration(), 1.5, timedelta(seconds=1.5)),
        (Duration(), "1s", timedelta(seconds=1)),
    ],
)
def test_duration_type(param_type, value, expected):
    assert param_type.convert(value, None, None) == expected


@pytest.mark.parametrize(
    "param_type,value,expected",
    [
        (Duration(), "abc", "Invalid duration: 'abc'"),
    ],
)
def test_duration_type_fail(param_type, value, expected):
    with pytest.raises(click.BadParameter) as exc_info:
        param_type.convert(value, None, None)

    assert expected in exc_info.value.message
