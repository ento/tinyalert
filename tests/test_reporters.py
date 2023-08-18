from unittest.mock import MagicMock

import pytest

from tinyalert.reporters import (
    DiffReporter,
    ListReporter,
    StatusReporter,
    TableReporter,
)
from tinyalert.types import ReportData


def test_table_reporter_outputs(snapshot):
    reporter = TableReporter()
    reporter.add(ReportData(metric_name="null"))
    reporter.add(
        ReportData(
            metric_name="kitchen-sink",
            latest_value=2,
            previous_value=1,
            latest_values=[0, 1, 2],
            absolute_max=0,
            absolute_min=3,
            relative_max=0,
            relative_min=2,
            latest_url="http://example.com/latest",
            previous_url="http://example.com/prev",
        )
    )

    assert reporter.get_value() == snapshot


def test_table_reporter_omits_details_column_when_possible(snapshot):
    reporter = TableReporter()
    reporter.add(ReportData(metric_name="null"))

    assert reporter.get_value() == snapshot


def test_list_reporter_outputs(snapshot):
    reporter = ListReporter()
    reporter.add(ReportData(metric_name="null"))
    reporter.add(
        ReportData(
            metric_name="kitchen-sink",
            latest_value=2,
            previous_value=1,
            latest_values=[0, 1, 2],
            absolute_max=0,
            absolute_min=3,
            relative_max=0,
            relative_min=2,
            latest_url="http://example.com/latest",
            previous_url="http://example.com/prev",
        )
    )

    assert reporter.get_value() == snapshot


def test_diff_reporter_outputs(snapshot):
    reporter = DiffReporter()
    reporter.add(ReportData(metric_name="null"))
    reporter.add(
        ReportData(
            metric_name="kitchen-sink",
            latest_value=2,
            absolute_max=0,
            latest_diffable_content="aaa",
            previous_diffable_content="bbb",
        )
    )

    assert reporter.get_value() == snapshot


def test_diff_reporter_outputs_nothing_when_no_diffable_content(snapshot):
    reporter = DiffReporter()
    reporter.add(
        ReportData(
            metric_name="kitchen-sink",
            latest_value=2,
            absolute_max=0,
            latest_diffable_content=None,
            previous_diffable_content=None,
        )
    )

    assert reporter.get_value() == snapshot


@pytest.mark.parametrize(
    "violations,expected",
    [
        ([], True),
        ([False], True),
        ([True], False),
        ([True, False], False),
        ([False, True], False),
        ([False, False], True),
        ([True, True], False),
    ],
)
def test_status_reporter_outputs(violations, expected):
    reporter = StatusReporter()
    for violation in violations:
        reporter.add(MagicMock(violates_limits=violation))

    assert reporter.get_value() == expected
