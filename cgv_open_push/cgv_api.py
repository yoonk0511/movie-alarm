from typing import Any

from playwright.sync_api import APIRequestContext


class CgvApiError(RuntimeError):
    pass


class CgvApiClient:
    def __init__(
        self,
        request: APIRequestContext,
        co_cd: str,
    ) -> None:
        self._request = request
        self._co_cd = co_cd

    def _get_json(
        self,
        path: str,
        params: dict[str, str],
    ) -> dict[str, Any]:
        response = self._request.get(
            path,
            params=params,
            headers={
                "Accept": "application/json",
            },
            timeout=30_000,
        )

        if not response.ok:
            raise CgvApiError(
                "CGV API request failed: "
                f"status={response.status}, "
                f"url={response.url}, "
                f"body={response.text()[:500]}"
            )

        try:
            result = response.json()
        except Exception as error:
            raise CgvApiError(
                "CGV API returned invalid JSON: "
                f"url={response.url}"
            ) from error

        if not isinstance(result, dict):
            raise CgvApiError(
                "unexpected CGV API response type: "
                f"{type(result).__name__}"
            )

        return result

    def fetch_scheduled_dates(
        self,
        site_no: str,
    ) -> list[str]:
        result = self._get_json(
            path=(
                "/api/v1/booking/"
                "searchSiteScnscYmdListBySite"
            ),
            params={
                "coCd": self._co_cd,
                "siteNo": site_no,
            },
        )

        data = result.get("data") or []

        if not isinstance(data, list):
            raise CgvApiError(
                "scheduled-date response data is not a list"
            )

        dates: list[str] = []

        for row in data:
            if not isinstance(row, dict):
                continue

            scn_ymd = row.get("scnYmd")

            if scn_ymd:
                dates.append(str(scn_ymd))

        return dates

    def fetch_showtimes(
        self,
        site_no: str,
        scn_ymd: str,
    ) -> list[dict[str, Any]]:
        result = self._get_json(
            path=(
                "/api/v1/booking/"
                "searchMovScnInfo"
            ),
            params={
                "coCd": self._co_cd,
                "siteNo": site_no,
                "scnYmd": scn_ymd,
                "rtctlScopCd": "08",
            },
        )

        data = result.get("data") or []

        if not isinstance(data, list):
            raise CgvApiError(
                "showtime response data is not a list"
            )

        return [
            entry
            for entry in data
            if isinstance(entry, dict)
        ]
