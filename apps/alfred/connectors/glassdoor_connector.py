"""Thin client for the OpenWeb Ninja Real-Time Glassdoor Data API."""

from __future__ import annotations

import json
import math
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin

import requests
from pydantic import BaseModel

from alfred.core.settings import settings


class GlassdoorResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None  # normalized leaf payload
    error: Optional[str] = None
    status_code: Optional[int] = None


def _unwrap(obj: Any) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Docs/examples show bodies like:
      {"status":"OK","parameters":{...},"data": {...}}
    We normalize to (success, data_dict).
    """
    if not isinstance(obj, dict):
        return False, None
    data = obj.get("data")
    success = (obj.get("status") == "OK") or bool(obj.get("success", True))
    if isinstance(data, dict):
        return success, data
    return success, obj  # fallback to raw dict if no "data"


def _best_company_match(query: str, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Pick the best match in ONE pass (no extra requests):
      1) exact case-insensitive name match
      2) startswith match
      3) contains match
      4) otherwise highest review_count, then highest rating
    """
    q = (query or "").strip().lower()
    if not candidates:
        return None

    def key_tuple(item: Dict[str, Any]) -> Tuple[int, float]:
        # For fallback sorting: (review_count, rating)
        return (
            int(item.get("review_count") or 0),
            float(item.get("rating") or 0.0),
        )

    exact = [c for c in candidates if (c.get("name") or "").strip().lower() == q]
    if exact:
        return sorted(exact, key=key_tuple, reverse=True)[0]

    starts = [c for c in candidates if (c.get("name") or "").strip().lower().startswith(q)]
    if starts:
        return sorted(starts, key=key_tuple, reverse=True)[0]

    contains = [c for c in candidates if q in (c.get("name") or "").strip().lower()]
    if contains:
        return sorted(contains, key=key_tuple, reverse=True)[0]

    # Fallback: overall strongest presence
    return sorted(candidates, key=key_tuple, reverse=True)[0]


class GlassdoorClient:
    def __init__(
        self,
        base_url: str = settings.openweb_ninja_base_url,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        user_agent: str = "gd-client/1.0",
        default_domain: str = "www.glassdoor.com",
    ):
        self.base_url = base_url.rstrip("/")
        # Prefer explicitly passed key, then settings, then alt env var for backward-compat
        self.api_key = (
            api_key or settings.openweb_ninja_api_key or settings.openweb_ninja_glassdoor_api_key
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.user_agent = user_agent
        self.default_domain = default_domain

    # ---------------- core http ----------------

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> GlassdoorResponse:
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        attempt = 0
        while True:
            attempt += 1
            try:
                r = requests.request(
                    method, url, headers=self._headers(), params=params, timeout=self.timeout
                )
                # success path
                try:
                    raw: Any = r.json()
                except ValueError:
                    raw = r.text

                if 200 <= r.status_code < 300:
                    if isinstance(raw, dict):
                        ok, unwrapped = _unwrap(raw)
                        return GlassdoorResponse(
                            success=ok, data=unwrapped, status_code=r.status_code
                        )
                    return GlassdoorResponse(
                        success=True, data={"raw": raw}, status_code=r.status_code
                    )

                # handle retryable errors (429/5xx)
                if r.status_code in (429, 500, 502, 503, 504) and attempt <= self.max_retries:
                    retry_after = r.headers.get("Retry-After")
                    if retry_after:
                        try:
                            sleep_s = float(retry_after)
                        except ValueError:
                            sleep_s = self.backoff_base * (2 ** (attempt - 1))
                    else:
                        sleep_s = self.backoff_base * (2 ** (attempt - 1))
                    time.sleep(sleep_s)
                    continue

                # non-OK final
                err_msg = raw if isinstance(raw, str) else json.dumps(raw)
                return GlassdoorResponse(success=False, error=err_msg, status_code=r.status_code)

            except requests.RequestException as exc:
                if attempt <= self.max_retries:
                    time.sleep(self.backoff_base * (2 ** (attempt - 1)))
                    continue
                return GlassdoorResponse(success=False, error=str(exc))

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> GlassdoorResponse:
        return self._request("GET", endpoint, params=params)

    # ---------------- endpoints ----------------

    def company_search(
        self,
        query: str,
        *,
        limit: int = 10,
        domain: Optional[str] = None,
    ) -> GlassdoorResponse:
        params = {
            "query": query,
            "limit": str(limit),
            "domain": domain or self.default_domain,
        }
        return self.get("/company-search", params=params)

    def company_interviews_page(
        self,
        company_id: Union[int, str],
        *,
        page: int = 1,
        sort: str = "POPULAR",  # POPULAR | MOST_RECENT | OLDEST | EASIEST | MOST_DIFFICULT | RELEVANCE
        job_function: str = "ANY",  # as per docs
        job_title: str = "",
        location: str = "",
        location_type: str = "ANY",  # ANY | CITY | STATE | COUNTRY
        received_offer_only: Optional[bool] = None,
        domain: Optional[str] = None,
    ) -> GlassdoorResponse:
        params: Dict[str, Any] = {
            "company_id": str(company_id),
            "page": str(page),
            "sort": sort,
            "job_function": job_function,
            "job_title": job_title,
            "location": location,
            "location_type": location_type,
            "domain": domain or self.default_domain,
        }
        if received_offer_only is not None:
            params["received_offer_only"] = str(bool(received_offer_only))
        return self.get("/company-interviews", params=params)

    # ---------------- high-level helpers ----------------

    def resolve_company_id(
        self,
        company: Union[int, str],
        *,
        search_limit: int = 10,
        domain: Optional[str] = None,
    ) -> Tuple[Optional[int], Optional[GlassdoorResponse]]:
        """
        Resolve the provided identifier and return (company_id, error_response).
        """
        if isinstance(company, int):
            return company, None

        comp_str = (company or "").strip()
        if comp_str.isdigit():
            return int(comp_str), None

        search = self.company_search(comp_str, limit=search_limit, domain=domain)
        if not search.success:
            return None, search

        payload = search.data or {}
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            err = GlassdoorResponse(
                success=False,
                error="Company search returned no candidates",
                status_code=search.status_code,
            )
            return None, err

        best = _best_company_match(comp_str, rows)
        if best and "company_id" in best:
            try:
                return int(best["company_id"]), None
            except (TypeError, ValueError):
                pass

        err = GlassdoorResponse(
            success=False,
            error="Company search did not return a usable company_id",
            status_code=search.status_code,
        )
        return None, err

    def get_company_interviews(
        self,
        company: Union[int, str],
        *,
        max_interviews: int = 50,
        # filters below are passed to /company-interviews
        sort: str = "POPULAR",
        job_function: str = "ANY",
        job_title: str = "",
        location: str = "",
        location_type: str = "ANY",
        received_offer_only: Optional[bool] = None,
        domain: Optional[str] = None,
    ) -> GlassdoorResponse:
        """
        Fetch up to `max_interviews` interview entries with minimal requests.
        - Resolves company_id in ONE search (if you passed a name).
        - Calls page 1 to get counts and compute how many pages are needed.
        - Pulls only as many pages as necessary (10 items/page).
        Returns:
           { "company_id": int, "interviews": [ ... ], "total_count": int, "page_count": int }
        """
        company_id, resolution = self.resolve_company_id(company, domain=domain)
        if not company_id:
            if resolution is not None:
                return resolution
            return GlassdoorResponse(success=False, error="Could not resolve company_id")

        first = self.company_interviews_page(
            company_id,
            page=1,
            sort=sort,
            job_function=job_function,
            job_title=job_title,
            location=location,
            location_type=location_type,
            received_offer_only=received_offer_only,
            domain=domain,
        )
        if not (first.success and first.data):
            return first  # contains error/status_code

        data = first.data
        interviews: List[Dict[str, Any]] = []
        page_payload = data.get("interviews") or data.get("reviews") or []  # defensive
        if isinstance(page_payload, list):
            interviews.extend(page_payload)

        total_count = int(data.get("total_count") or data.get("filtered_count") or len(interviews))
        page_count = int(data.get("page_count") or math.ceil(max(total_count, 1) / 10))

        # How many pages do we *actually* need?
        need = max_interviews if max_interviews and max_interviews > 0 else total_count
        pages_needed = min(page_count, math.ceil(need / 10))

        # Already have page 1; fetch pages 2..N as needed
        for p in range(2, pages_needed + 1):
            page = self.company_interviews_page(
                company_id,
                page=p,
                sort=sort,
                job_function=job_function,
                job_title=job_title,
                location=location,
                location_type=location_type,
                received_offer_only=received_offer_only,
                domain=domain,
            )
            if not (page.success and page.data):
                # Return what we have so far (partial success) with error note
                return GlassdoorResponse(
                    success=True,
                    data={
                        "company_id": company_id,
                        "interviews": interviews,
                        "total_count": total_count,
                        "page_count": page_count,
                        "note": f"Stopped at page {p} due to: {page.error or page.status_code}",
                    },
                    status_code=page.status_code,
                )
            payload = page.data.get("interviews") or page.data.get("reviews") or []
            if isinstance(payload, list):
                interviews.extend(payload)
            if len(interviews) >= need:
                break

        # Truncate to exactly max_interviews if we over-fetched on last page
        if need and len(interviews) > need:
            interviews = interviews[:need]

        return GlassdoorResponse(
            success=True,
            data={
                "company_id": company_id,
                "interviews": interviews,
                "total_count": total_count,
                "page_count": page_count,
            },
            status_code=200,
        )


if __name__ == "__main__":
    client = GlassdoorClient(
        base_url=settings.openweb_ninja_base_url,
        api_key=settings.openweb_ninja_api_key
        or settings.openweb_ninja_glassdoor_api_key
        or settings.openweb_ninja_glassdoor_api_key,
    )

    res = client.get_company_interviews(
        "Hubspot",  # or 9079
        max_interviews=30,
        sort="MOST_RECENT",
        location="San-Francisco",  # optional
        location_type="CITY",
    )
    print("Success:", res.success, "Status:", res.status_code)
    if res.success and res.data:
        print("Company ID:", res.data.get("company_id"))
        print("Fetched interviews:", len(res.data.get("interviews", [])))
        print("Total interviews (reported):", res.data.get("total_count"))
        print("Page count (reported):", res.data.get("page_count"))
    else:
        print("Error:", res.error)
