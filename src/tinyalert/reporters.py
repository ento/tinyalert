import difflib
import textwrap

from tabulate import tabulate
from termcolor import colored

from .types import GenerationMatchStatus, MetricDiff, ReportData


class TableReporter:
    header = dict(
        status_character="",
        metric_name="Name",
        latest_value="Value",
        abs_limits="Thresholds",
        change="Change",
        rel_limits="Thresholds",
        details="Details",
    )

    def __init__(self):
        self.rows = []

    def add(self, report_data: ReportData) -> None:
        self.rows.append(self._make_row(report_data))

    def _make_row(self, report_data: ReportData) -> dict:
        row = dict(
            status_character=report_data.status_character,
            metric_name=report_data.metric_name,
            latest_value="-",
            abs_limits="-",
            change="-",
            rel_limits="-",
            details="",
        )

        if report_data.latest_value is not None:
            value_string = f"{report_data.latest_value:g}"
            colored_value_string = (
                (colored(value_string, "red") + " [!]")
                if report_data.violates_absolute_limits
                else value_string
            )
            row["latest_value"] = colored_value_string

        if (
            report_data.previous_value is not None
            and report_data.generation_status != GenerationMatchStatus.NONE_MATCHED
        ):
            change_string = f"{report_data.latest_change:+g}"
            colored_change_string = (
                (colored(change_string, "yellow") + " [!]")
                if report_data.violates_relative_limits
                else change_string
            )
            row["change"] = colored_change_string

        if (report_data.absolute_min is not None) or (
            report_data.absolute_max is not None
        ):
            abs_thresholds = []
            if report_data.absolute_min is not None:
                abs_thresholds.append(f"{report_data.absolute_min}<=v")
            if report_data.absolute_max is not None:
                abs_thresholds.append(f"v<={report_data.absolute_max}")
            row["abs_limits"] = ", ".join(abs_thresholds)

        if (report_data.relative_min is not None) or (
            report_data.relative_max is not None
        ):
            rel_thresholds = []
            if report_data.relative_min is not None:
                rel_thresholds.append(f"{report_data.relative_min}<=Δ")
            if report_data.relative_max is not None:
                rel_thresholds.append(f"Δ<={report_data.relative_max}")
            row["rel_limits"] = ", ".join(rel_thresholds)

        details = []
        if (
            report_data.previous_url
            and report_data.generation_status != GenerationMatchStatus.NONE_MATCHED
        ):
            details.append(f"[baseline]({report_data.previous_url})")
        if report_data.latest_url:
            title = (
                "baseline"
                if report_data.generation_status == GenerationMatchStatus.NONE_MATCHED
                else "latest"
            )
            details.append(f"[{title}]({report_data.latest_url})")
        row["details"] = " \| ".join(details)

        return row

    def get_value(self) -> str:
        header = dict(self.header)
        rows = [dict(row) for row in self.rows]
        if not any(row["details"] for row in rows):
            del header["details"]
            for row in rows:
                del row["details"]
        return tabulate(rows, header, tablefmt="github")


class ListReporter:
    def __init__(self):
        self.items = []

    def add(self, report_data: ReportData) -> None:
        if report_data.violates_absolute_max:
            self.items.append(
                (
                    f"{report_data.metric_name} latest value {report_data.latest_value:g}:"
                    f" violates absolute max value of {report_data.absolute_max:g}"
                )
            )

        if report_data.violates_absolute_min:
            self.items.append(
                (
                    f"{report_data.metric_name} latest value {report_data.latest_value:g}:"
                    f" violates absolute min value of {report_data.absolute_min:g}"
                )
            )

        if report_data.violates_relative_max:
            self.items.append(
                (
                    f"{report_data.metric_name} changed by {report_data.latest_change:+g}:"
                    f" violates relative max value of {report_data.relative_max:+g}"
                )
            )

        if report_data.violates_relative_min:
            self.items.append(
                (
                    f"{report_data.metric_name} changed by {report_data.latest_change:+g}:"
                    f" violates relative min value of {report_data.relative_min:+g}"
                )
            )

    def get_value(self) -> str:
        return "\n".join([f"- {message}" for message in self.items])


class DiffReporter:
    def __init__(self):
        self.diffs = []

    def add(self, report_data: ReportData) -> None:
        if not report_data.violates_limits:
            return
        latest_lines = (
            report_data.latest_diffable_content.splitlines(keepends=False)
            if report_data.latest_diffable_content is not None
            else []
        )
        previous_lines = (
            report_data.previous_diffable_content.splitlines(keepends=False)
            if report_data.previous_diffable_content is not None
            else []
        )
        diff = difflib.unified_diff(
            previous_lines, latest_lines, "previous", "latest", lineterm=""
        )
        self.diffs.append(
            MetricDiff(metric_name=report_data.metric_name, diff="\n".join(diff))
        )

    def get_value(self) -> str:
        return "\n".join(
            [self._format_metric_diff(diff) for diff in self.diffs if diff.diff]
        )

    def _format_metric_diff(self, metric_diff: MetricDiff) -> str:
        return textwrap.dedent(
            """
        <details><summary>{metric_name} diff</summary>

        ```diff
        {diff}
        ```

        </details>
        """
        ).format(**metric_diff.model_dump())


class StatusReporter:
    def __init__(self):
        self.success = True

    def add(self, report_data: ReportData) -> None:
        if report_data.violates_limits:
            self.success = False

    def get_value(self) -> bool:
        return self.success
