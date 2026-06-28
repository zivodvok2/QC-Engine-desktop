"""
iField API connector — stub for future production integration.

Feature flag: set USE_IFIELD_API=true in environment to activate.
When false (default), the dashboard falls back to manual Excel uploads.

Usage (future):
    from data.ifield_connector import IFieldClient
    client = IFieldClient(base_url=os.environ["IFIELD_URL"], api_key=os.environ["IFIELD_KEY"])
    data = client.fetch_quality_report(project_id="P001", date_from="2025-01-01", date_to="2025-04-30")
"""

import os

USE_IFIELD_API = os.environ.get("USE_IFIELD_API", "false").lower() == "true"


class IFieldClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _get(self, endpoint: str, params: dict = None):
        raise NotImplementedError("iField API integration is not yet active.")

    def fetch_quality_report(self, project_id: str, date_from: str, date_to: str) -> list[dict]:
        """Fetch TOPLINE QUALITY CHECKS data for a project and date range."""
        raise NotImplementedError("iField API integration is not yet active.")

    def fetch_backcheck_report(self, project_id: str, date_from: str, date_to: str) -> list[dict]:
        """Fetch OM_BackCheckResultReport data for a project and date range."""
        raise NotImplementedError("iField API integration is not yet active.")

    def fetch_performance_report(self, project_id: str, date_from: str, date_to: str) -> list[dict]:
        """Fetch Project Performance Report data."""
        raise NotImplementedError("iField API integration is not yet active.")

    def fetch_timing_report(self, project_id: str, date_from: str, date_to: str) -> list[dict]:
        """Fetch TimingReportDataExport data."""
        raise NotImplementedError("iField API integration is not yet active.")
