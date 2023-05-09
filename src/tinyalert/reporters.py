import difflib

from sparklines import sparklines
from tabulate import tabulate
from termcolor import colored

from .types import MetricDiff, ReportData


class TableReporter:
    # TODO: add room for relative thresholds
    header = ["Name", "Value", "Diff", "Threshold", "Trend", "Details"]

    def __init__(self):
        self.rows = []

    def add(self, report_data: ReportData) -> None:
        row = [report_data.metric_name]

        if not report_data.latest_values:
            row.append("-")
            row.append("-")
            row.append("-")
            self.rows.append(row)
            return

        if report_data.latest_value is None:
            row.append("-")
            row.append("-")
            row.append("-")
            self.rows.append(row)
            return

        value_string = f"{report_data.latest_value:g}"
        colored_value_string = (
            (colored(value_string, "red") + " [!]")
            if report_data.violates_absolute_limits
            else value_string
        )
        row.append(colored_value_string)

        if report_data.previous_value is None:
            row.append("-")
        else:
            change_string = f"{report_data.latest_change:+g}"
            colored_change_string = (
                (colored(change_string, "yellow") + " [!]")
                if report_data.violates_relative_limits
                else change_string
            )
            row.append(colored_change_string)

        thresholds = []
        if report_data.absolute_min is not None:
            thresholds.append(f"{report_data.absolute_min}<=")
        if report_data.absolute_max is not None:
            thresholds.append(f"<={report_data.absolute_max}")
        if not thresholds:
            thresholds.append("-")
        row.append(", ".join(thresholds))

        row.append(sparklines(report_data.latest_values)[0])

        if report_data.url:
            row.append(f"[Details]({report_data.url})")
        else:
            row.append("")

        self.rows.append(row)

    def get_value(self) -> str:
        return tabulate(self.rows, self.header, tablefmt="github")


class ListReporter:
    def __init__(self):
        self.items = []

    def add(self, report_data: ReportData) -> None:
        # TODO: add relative violation
        if report_data.violates_absolute_max:
            self.items.append(
                (
                    f"{report_data.metric_name}: {report_data.latest_value:g}"
                    f" violates absolute max value of {report_data.absolute_max:g}"
                )
            )

        if report_data.violates_absolute_min:
            self.items.append(
                (
                    f"{report_data.metric_name}: {report_data.latest_value:g}"
                    f" violates absolute min value of {report_data.absolute_min:g}"
                )
            )

    def get_value(self) -> str:
        return "\n".join([f"- {message}" for message in self.items])


class DiffReporter:
    def __init__(self):
        self.diffs = []

    def add(self, report_data: ReportData) -> None:
        latest_lines = (
            report_data.latest_content.splitlines(keepends=True)
            if report_data.latest_diffable_content is not None
            else []
        )
        previous_lines = (
            report_data.previous_content.splitlines(keepends=True)
            if report_data.previous_diffable_content is not None
            else []
        )
        diff = difflib.unified_diff(previous_lines, latest_lines, "previous", "latest")
        self.diffs.append(
            MetricDiff(metric_name=report_data.metric_name, diff="".join(diff))
        )

    def get_value(self) -> str:
        return "\n".join([diff.diff for diff in self.diffs])


class StatusReporter:
    def __init__(self):
        self.success = True

    def add(self, report_data: ReportData) -> None:
        if report_data.violates_limits:
            self.success = False

    def get_value(self) -> bool:
        return self.success
