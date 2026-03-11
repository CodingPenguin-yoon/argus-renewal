from __future__ import annotations

from dataclasses import dataclass
import io
import logging
import time
import xml.etree.ElementTree as ET
import zipfile

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DartCompanyRecord:
    corp_code: str
    corp_name: str
    corp_eng_name: str | None
    stock_code: str | None
    modify_date: str | None
    source_url: str


class DartClient:
    def __init__(
        self,
        *,
        api_key: str,
        corp_code_url: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.corp_code_url = corp_code_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client

    def fetch_company_master(self) -> list[DartCompanyRecord]:
        if not self.api_key:
            raise ValueError("DART API key is required")

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "dart_master_fetch_attempt",
                    extra={"attempt": attempt, "url": self.corp_code_url},
                )
                response = self._request_corp_master()
                response.raise_for_status()
                records = self._parse_zip_payload(response.content)
                logger.info(
                    "dart_master_fetch_success",
                    extra={"count": len(records), "attempt": attempt},
                )
                return records
            except (httpx.HTTPError, ET.ParseError, zipfile.BadZipFile, ValueError) as error:
                last_error = error
                logger.warning(
                    "dart_master_fetch_failed",
                    extra={"attempt": attempt, "error": str(error)},
                )
                if attempt < self.max_retries:
                    sleep_seconds = self.backoff_seconds * (2 ** (attempt - 1))
                    time.sleep(sleep_seconds)

        raise RuntimeError("Failed to fetch DART company master after retries") from last_error

    def _request_corp_master(self) -> httpx.Response:
        params = {"crtfc_key": self.api_key}
        if self._http_client is not None:
            return self._http_client.get(
                self.corp_code_url,
                params=params,
                timeout=self.timeout_seconds,
            )
        with httpx.Client() as client:
            return client.get(
                self.corp_code_url,
                params=params,
                timeout=self.timeout_seconds,
            )

    def _parse_zip_payload(self, payload: bytes) -> list[DartCompanyRecord]:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            xml_members = [name for name in archive.namelist() if name.lower().endswith(".xml")]
            if not xml_members:
                raise ValueError("DART payload did not include XML file")

            raw_xml = archive.read(xml_members[0])

        root = ET.fromstring(raw_xml)
        records: list[DartCompanyRecord] = []

        for element in root.findall("list"):
            corp_code = (element.findtext("corp_code") or "").strip()
            corp_name = (element.findtext("corp_name") or "").strip()
            if not corp_code or not corp_name:
                continue

            records.append(
                DartCompanyRecord(
                    corp_code=corp_code,
                    corp_name=corp_name,
                    corp_eng_name=(element.findtext("corp_eng_name") or "").strip() or None,
                    stock_code=(element.findtext("stock_code") or "").strip() or None,
                    modify_date=(element.findtext("modify_date") or "").strip() or None,
                    source_url=self.corp_code_url,
                )
            )

        return records
