"""Google Sheet destination.

description: Upsert internal records to a Google Sheet keyed by internal_id.
inputs:      destination.target = sheet ID; GOOGLE_SERVICE_ACCOUNT_JSON env
outputs:     rows added / updated in the first worksheet of the target sheet.

Requires: google-api-python-client, google-auth. Install per requirements.txt.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from .base import Destination


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetDestination(Destination):
    def __init__(self, tenant_config: dict[str, Any]) -> None:
        super().__init__(tenant_config)
        target = tenant_config.get("destination", {}).get("target") or os.environ.get(
            "DESTINATION_SHEET_ID"
        )
        if not target:
            raise RuntimeError("google_sheet destination requires destination.target = <sheet_id>")
        self._sheet_id = target
        self._creds_path = Path(
            os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "./credentials.json")
        )
        if not self._creds_path.exists():
            raise RuntimeError(
                f"GOOGLE_SERVICE_ACCOUNT_JSON not found at {self._creds_path}"
            )
        self._lock = threading.Lock()
        self._service = self._build_service()
        self._id_col = self._resolve_id_column()

    def _build_service(self):
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "google-api-python-client + google-auth required. "
                "pip install google-api-python-client google-auth"
            ) from e
        creds = Credentials.from_service_account_file(str(self._creds_path), scopes=SCOPES)
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

    def _resolve_id_column(self) -> int:
        """Read the header row; find the 'internal_id' column index (0-based).
        If the sheet is empty, write a header from the tenant's field mapping.
        """
        with self._lock:
            r = (
                self._service.spreadsheets()
                .values()
                .get(spreadsheetId=self._sheet_id, range="A1:Z1")
                .execute()
            )
            values = r.get("values") or []
            if values and "internal_id" in values[0]:
                return values[0].index("internal_id")
            # Empty or misheaded — seed header from mapping keys.
            mapping_keys = list(self.config.get("field_mappings", {}).keys())
            header = ["internal_id", "watermark", "record_type", "_provider", *mapping_keys]
            self._service.spreadsheets().values().update(
                spreadsheetId=self._sheet_id,
                range="A1",
                valueInputOption="RAW",
                body={"values": [header]},
            ).execute()
            return 0

    def _find_row_for_id(self, internal_id: str) -> int | None:
        """1-based row number where column A == internal_id, or None."""
        with self._lock:
            r = (
                self._service.spreadsheets()
                .values()
                .get(spreadsheetId=self._sheet_id, range="A2:A100000")
                .execute()
            )
            values = r.get("values") or []
        for i, row in enumerate(values, start=2):
            if row and row[0] == internal_id:
                return i
        return None

    def upsert(self, internal_record: dict[str, Any]) -> str:
        # Header order: internal_id | watermark | record_type | _provider | mapped-keys...
        mapping_keys = list(self.config.get("field_mappings", {}).keys())
        row = [
            str(internal_record.get("internal_id") or ""),
            str(internal_record.get("watermark") or ""),
            str(internal_record.get("record_type") or ""),
            str(internal_record.get("_provider") or ""),
        ]
        for k in mapping_keys:
            v = internal_record.get(k)
            row.append("" if v is None else str(v))

        existing = self._find_row_for_id(str(internal_record.get("internal_id") or ""))
        with self._lock:
            if existing is None:
                self._service.spreadsheets().values().append(
                    spreadsheetId=self._sheet_id,
                    range="A1",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [row]},
                ).execute()
                return "created"
            self._service.spreadsheets().values().update(
                spreadsheetId=self._sheet_id,
                range=f"A{existing}",
                valueInputOption="RAW",
                body={"values": [row]},
            ).execute()
            return "updated"

    def close(self) -> None:
        pass
