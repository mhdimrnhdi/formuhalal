"""Scrape company listings from the My e-Halal certified directory."""

from __future__ import annotations

import json
import logging
import os
import re
import ssl
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

LOGGER = logging.getLogger(__name__)

FIRST_PAGE_URL = "https://myehalal.halal.gov.my/portal-halal/v1/index.php?data=ZGlyZWN0b3J5L2luZGV4X2RpcmVjdG9yeTs7Ozs="
DEFAULT_SUPPLIER_URL = FIRST_PAGE_URL
HALAL_PORTAL_ORIGIN = "https://myehalal.halal.gov.my/portal-halal/v1/"
HALAL_DIRECTORY_DATA = "ZGlyZWN0b3J5L2luZGV4X2RpcmVjdG9yeTs7Ozs="
LAST_DIRECTORY_PAGE = 546
WHITESPACE_RE = re.compile(r"\s+")
COMP_CODE_RE = re.compile(r"comp_code=([^&'\"]+)")
REQUEST_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
RETRY_DELAY_SECONDS = 3.0
USER_AGENT = "FormuHalal-ETL/1.0 (+https://github.com/formuhalal)"


def _halal_portal_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    context.set_ciphers("AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384")
    return context


def _normalize_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def _directory_page_url(page: int) -> str:
    if page <= 1:
        return FIRST_PAGE_URL
    return f"{HALAL_PORTAL_ORIGIN}index.php?data={HALAL_DIRECTORY_DATA}&negeri=&category=&page={page}&cari="


def _fetch_html(client: httpx.Client, url: str) -> str:
    """Fetch a directory page, retrying every 3s while the server returns HTTP 500."""
    while True:
        response = client.get(url, headers={"User-Agent": USER_AGENT})
        if response.status_code == 500:
            LOGGER.warning("HTTP 500 for %s; retrying in %ss", url, RETRY_DELAY_SECONDS)
            time.sleep(RETRY_DELAY_SECONDS)
            continue
        response.raise_for_status()
        return response.text


def _extract_companies(soup: BeautifulSoup, page_url: str) -> list[dict[str, str]]:
    companies: list[dict[str, str]] = []

    for row in soup.select("table.w-full tr"):
        onclick = row.get("onclick", "")
        code_match = COMP_CODE_RE.search(onclick)
        name_element = row.select_one(".company-name")
        if code_match is None or name_element is None:
            continue

        company_id = code_match.group(1)
        name = _normalize_text(name_element.get_text(" ", strip=True))
        if not name:
            continue

        detail_path = onclick.split("'")[1] if "'" in onclick else ""
        source_url = urljoin(HALAL_PORTAL_ORIGIN, detail_path) if detail_path else page_url
        address_element = row.select_one(".company-address")
        address = _normalize_text(address_element.get_text(" ", strip=True)) if address_element else ""

        companies.append(
            {
                "id": company_id,
                "name": name,
                "location": address,
                "certifications": "JAKIM Halal Directory",
                "source_url": source_url,
                "notes": "",
            }
        )

    return companies


def _crawl_halal_directory(client: httpx.Client) -> list[dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}

    LOGGER.info("Crawling directory pages 1-%s", LAST_DIRECTORY_PAGE)

    for page in range(1, LAST_DIRECTORY_PAGE + 1):
        page_url = _directory_page_url(page)
        page_html = _fetch_html(client, page_url)
        soup = BeautifulSoup(page_html, "html.parser")

        companies = _extract_companies(soup, page_url)

        LOGGER.info(
            "Page %s/%s: %s companies (%s total)",
            page,
            LAST_DIRECTORY_PAGE,
            len(companies),
            len(by_id),
        )

        if not companies:
            LOGGER.info("Page %s returned 0 companies; stopping crawl", page)
            break

        for company in companies:
            by_id[company["id"]] = company

    return list(by_id.values())


def crawl_suppliers(output_path: Path, source_url: str | None = None) -> int:
    target_url = source_url or os.getenv("SUPPLIER_CRAWL_URL") or DEFAULT_SUPPLIER_URL
    is_halal_portal = "myehalal.halal.gov.my" in target_url
    output_path.parent.mkdir(parents=True, exist_ok=True)

    suppliers: list[dict[str, str]] = []

    ssl_context = _halal_portal_ssl_context() if is_halal_portal else True
    with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True, verify=ssl_context) as client:
        if is_halal_portal:
            suppliers = _crawl_halal_directory(client)
        else:
            response = client.get(target_url, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            suppliers = _extract_companies(soup, target_url)

    if not suppliers:
        LOGGER.warning(
            "No companies extracted from %s; keeping existing supplier data and waiting for the next scheduled crawl",
            target_url,
        )
        return 0

    payload = {
        "scraped_at": datetime.now(UTC).isoformat(),
        "source": urlparse(target_url).netloc or target_url,
        "source_url": target_url,
        "suppliers": suppliers,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return len(suppliers)
