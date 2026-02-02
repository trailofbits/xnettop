"""Interactive TUI using textual."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import DataTable, Footer, Header, Static

if TYPE_CHECKING:
    from xnettop.aggregator import ProcessStats, TrafficAggregator


def format_bytes(num_bytes: float) -> str:
    """Format bytes as human-readable string."""
    if num_bytes < 1024:
        return f"{num_bytes:.0f} B/s"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB/s"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB/s"
    return f"{num_bytes / (1024 * 1024 * 1024):.1f} GB/s"


def format_total_bytes(num_bytes: int) -> str:
    """Format total bytes as human-readable string."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.1f} GB"


class SortColumn:
    """Enum-like class for sort columns."""

    DOWNLOAD = "download"
    UPLOAD = "upload"
    TOTAL = "total"
    NAME = "name"


class StatsDisplay(Static):
    """Widget displaying summary statistics."""

    def __init__(self) -> None:
        super().__init__()
        self._total_upload = 0
        self._total_download = 0
        self._upload_rate = 0.0
        self._download_rate = 0.0

    def update_stats(
        self,
        total_upload: int,
        total_download: int,
        upload_rate: float,
        download_rate: float,
    ) -> None:
        """Update the displayed stats."""
        self._total_upload = total_upload
        self._total_download = total_download
        self._upload_rate = upload_rate
        self._download_rate = download_rate
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the display text."""
        text = (
            f"Total: {format_bytes(self._upload_rate + self._download_rate)} | "
            f"Up: {format_bytes(self._upload_rate)} ({format_total_bytes(self._total_upload)}) | "
            f"Down: {format_bytes(self._download_rate)} ({format_total_bytes(self._total_download)})"
        )
        self.update(text)


class XnettopApp(App[None]):
    """Main xnettop TUI application."""

    CSS = """
    Screen {
        background: $surface;
    }
    #stats-display {
        dock: top;
        height: 1;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }
    #table-container {
        height: 1fr;
    }
    DataTable {
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "sort_download", "Sort Download"),
        Binding("u", "sort_upload", "Sort Upload"),
        Binding("t", "sort_total", "Sort Total"),
        Binding("n", "sort_name", "Sort Name"),
        Binding("c", "clear", "Clear"),
    ]

    def __init__(self, aggregator: TrafficAggregator, refresh_rate: float = 1.0) -> None:
        super().__init__()
        self._aggregator = aggregator
        self._refresh_rate = refresh_rate
        self._sort_column = SortColumn.TOTAL
        self._sort_reverse = True

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header()
        yield StatsDisplay(id="stats-display")
        yield Container(DataTable(id="traffic-table"), id="table-container")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the table and start refresh timer."""
        table = self.query_one("#traffic-table", DataTable)
        table.add_columns("Process", "PID", "Download", "Upload", "Total", "Total Down", "Total Up")
        table.cursor_type = "row"
        self.set_interval(self._refresh_rate, self._refresh_table)

    def _refresh_table(self) -> None:
        """Refresh the traffic table."""
        table = self.query_one("#traffic-table", DataTable)
        stats = self._aggregator.get_stats()
        stats = self._sort_stats(stats)
        table.clear()
        total_upload_rate = 0.0
        total_download_rate = 0.0
        total_upload_bytes = 0
        total_download_bytes = 0
        for stat in stats:
            if stat.upload_rate < 1 and stat.download_rate < 1:
                if stat.upload_bytes == 0 and stat.download_bytes == 0:
                    continue
            total_rate = stat.upload_rate + stat.download_rate
            table.add_row(
                stat.name[:30],
                str(stat.pid) if stat.pid >= 0 else "?",
                format_bytes(stat.download_rate),
                format_bytes(stat.upload_rate),
                format_bytes(total_rate),
                format_total_bytes(stat.download_bytes),
                format_total_bytes(stat.upload_bytes),
            )
            total_upload_rate += stat.upload_rate
            total_download_rate += stat.download_rate
            total_upload_bytes += stat.upload_bytes
            total_download_bytes += stat.download_bytes
        stats_display = self.query_one("#stats-display", StatsDisplay)
        stats_display.update_stats(
            total_upload_bytes, total_download_bytes, total_upload_rate, total_download_rate
        )

    def _sort_stats(self, stats: list[ProcessStats]) -> list[ProcessStats]:
        """Sort stats by the current sort column."""
        if self._sort_column == SortColumn.DOWNLOAD:
            key = lambda s: s.download_rate
        elif self._sort_column == SortColumn.UPLOAD:
            key = lambda s: s.upload_rate
        elif self._sort_column == SortColumn.TOTAL:
            key = lambda s: s.upload_rate + s.download_rate
        else:
            key = lambda s: s.name.lower()
        return sorted(stats, key=key, reverse=self._sort_reverse)

    def action_sort_download(self) -> None:
        """Sort by download rate."""
        if self._sort_column == SortColumn.DOWNLOAD:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = SortColumn.DOWNLOAD
            self._sort_reverse = True
        self._refresh_table()

    def action_sort_upload(self) -> None:
        """Sort by upload rate."""
        if self._sort_column == SortColumn.UPLOAD:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = SortColumn.UPLOAD
            self._sort_reverse = True
        self._refresh_table()

    def action_sort_total(self) -> None:
        """Sort by total rate."""
        if self._sort_column == SortColumn.TOTAL:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = SortColumn.TOTAL
            self._sort_reverse = True
        self._refresh_table()

    def action_sort_name(self) -> None:
        """Sort by process name."""
        if self._sort_column == SortColumn.NAME:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = SortColumn.NAME
            self._sort_reverse = False
        self._refresh_table()

    def action_clear(self) -> None:
        """Clear accumulated stats."""
        self._aggregator.clear_stats()
        self._refresh_table()
