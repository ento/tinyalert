import pytest

from tinyalert.types import ReportData, GenerationMatchStatus


@pytest.mark.parametrize(
    "abs_max,value,expected",
    [
        (None, None, False),
        (None, 1, False),
        (0, 1, True),
        (0, None, False),
        (1, 1, False),
        (2, 1, False),
    ],
)
def test_report_data_violates_absolute_max(abs_max, value, expected):
    data = ReportData(metric_name="test", absolute_max=abs_max, latest_value=value)

    assert data.violates_absolute_max == expected


@pytest.mark.parametrize(
    "abs_min,value,expected",
    [
        (None, None, False),
        (None, 1, False),
        (0, 1, False),
        (1, 1, False),
        (2, 1, True),
        (2, None, False),
    ],
)
def test_report_data_violates_absolute_min(abs_min, value, expected):
    data = ReportData(metric_name="test", absolute_min=abs_min, latest_value=value)

    assert data.violates_absolute_min == expected


@pytest.mark.parametrize(
    "rel_max,value,prev,expected",
    [
        (None, None, None, False),
        (None, 1, None, False),
        (None, None, 1, False),
        (0, None, None, False),
        (0, 1, None, False),
        (0, None, 1, False),
        (0, 1, 1, False),
        (0, 2, 1, True),
        (0, 0, 1, False),
    ],
)
def test_report_data_violates_relative_max(rel_max, value, prev, expected):
    data = ReportData(
        metric_name="test",
        relative_max=rel_max,
        latest_value=value,
        previous_value=prev,
    )

    assert data.violates_relative_max == expected


@pytest.mark.parametrize(
    "rel_min,value,prev,expected",
    [
        (None, None, None, False),
        (None, 1, None, False),
        (None, None, 1, False),
        (0, None, None, False),
        (0, 1, None, False),
        (0, None, 1, False),
        (0, 1, 1, False),
        (0, 2, 1, False),
        (0, 0, 1, True),
    ],
)
def test_report_data_violates_relative_min(rel_min, value, prev, expected):
    data = ReportData(
        metric_name="test",
        relative_min=rel_min,
        latest_value=value,
        previous_value=prev,
    )

    assert data.violates_relative_min == expected


@pytest.mark.parametrize(
    "violates_max,violates_min,skipped,expected",
    [
        (True, True, False, True),
        (True, False, False, True),
        (False, True, False, True),
        (False, False, False, False),
        (True, True, True, True),
        (True, False, True, True),
        (False, True, True, True),
        (False, False, True, False),
    ],
)
def test_report_data_violates_absolute_limits(
    monkeypatch, violates_max, violates_min, skipped, expected
):
    data = ReportData.model_validate(dict(metric_name="test", skipped=skipped))
    monkeypatch.setattr(ReportData, "violates_absolute_max", violates_max)
    monkeypatch.setattr(ReportData, "violates_absolute_min", violates_min)

    assert data.violates_absolute_limits == expected


@pytest.mark.parametrize(
    "violates_max,violates_min,skipped,expected",
    [
        (True, True, False, True),
        (True, False, False, True),
        (False, True, False, True),
        (False, False, False, False),
        (True, True, True, True),
        (True, False, True, True),
        (False, True, True, True),
        (False, False, True, False),
    ],
)
def test_report_data_violates_relative_limits(
    monkeypatch, violates_max, violates_min, skipped, expected
):
    data = ReportData.model_validate(dict(metric_name="test", skipped=skipped))
    monkeypatch.setattr(ReportData, "violates_relative_max", violates_max)
    monkeypatch.setattr(ReportData, "violates_relative_min", violates_min)

    assert data.violates_relative_limits == expected


@pytest.mark.parametrize("gen_status,expected", [
    (GenerationMatchStatus.NONE_SPECIFIED, True),
    (GenerationMatchStatus.NONE_MATCHED, False),
    (GenerationMatchStatus.MATCHED, True),
])
def test_report_data_doesnt_violate_any_threshold_when_generation_doesnt_match(gen_status,expected):
    data = ReportData(
        metric_name="test",
        absolute_max=0,
        absolute_min=20,
        relative_max=0,
        relative_min=20,
        previous_value=0,
        latest_value=10,
        generation_status=gen_status,
    )

    assert data.violates_absolute_max is expected
    assert data.violates_absolute_min is expected
    assert data.violates_relative_max is expected
    assert data.violates_relative_min is expected


@pytest.mark.parametrize(
    "violates_abs,violates_rel,expected",
    [
        (True, True, True),
        (True, False, True),
        (False, True, True),
        (False, False, False),
    ],
)
def test_report_data_violates_limits(monkeypatch, violates_abs, violates_rel, expected):
    data = ReportData.model_validate(dict(metric_name="test"))
    monkeypatch.setattr(ReportData, "violates_absolute_limits", violates_abs)
    monkeypatch.setattr(ReportData, "violates_relative_limits", violates_rel)

    assert data.violates_limits == expected


@pytest.mark.parametrize(
    "value,prev,expected",
    [
        (None, None, None),
        (1, None, None),
        (None, 1, None),
        (1, 0, 1),
    ],
)
def test_report_data_latest_changes(monkeypatch, value, prev, expected):
    data = ReportData(metric_name="test", latest_value=value, previous_value=prev)

    assert data.latest_change == expected
