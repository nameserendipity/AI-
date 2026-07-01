"""CNINFO announcement adapter for the A-share data layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import aiohttp
from loguru import logger

from .schemas import Announcement
from .symbols import AStockSymbol, normalize_symbol

CNINFO_BASE = "http://www.cninfo.com.cn"
CNINFO_STATIC = "http://static.cninfo.com.cn"


class CNInfoAStockAdapter:
    """Fetch A-share announcements from CNINFO."""

    source = "cninfo"

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Host": "www.cninfo.com.cn",
            "Origin": CNINFO_BASE,
            "Referer": (
                CNINFO_BASE
                + "/new/commonUrl/pageOfSearch?url=disclosure/list/search&lastPage=index"
            ),
            "X-Requested-With": "XMLHttpRequest",
        }

    def _column(self, stock: AStockSymbol) -> str:
        if stock.exchange == "SZ":
            return "szse"
        if stock.exchange == "BJ":
            return "third"
        return "sse"

    def _plate(self, stock: AStockSymbol) -> str:
        if stock.exchange == "SZ":
            return "sz"
        if stock.exchange == "BJ":
            return "bj"
        return "sh"

    async def _get_org_id(
        self, stock: AStockSymbol, session: aiohttp.ClientSession
    ) -> str | None:
        url = f"{CNINFO_BASE}/new/information/topSearch/query"
        try:
            async with session.post(
                url,
                headers=self._headers(),
                data={"keyWord": stock.code},
            ) as response:
                if response.status != 200:
                    return None
                result = await response.json(content_type=None)
                if not result:
                    return None
                for item in result:
                    if item.get("code") == stock.code:
                        return item.get("orgId")
                return result[0].get("orgId")
        except Exception as exc:  # noqa: BLE001
            logger.warning("CNINFO orgId lookup failed for {}: {}", stock.canonical, exc)
            return None

    def _category(self, category: str | None) -> str:
        mapping = {
            "annual": "category_ndbg_szsh",
            "semi-annual": "category_bndbg_szsh",
            "quarterly": "category_sjdbg_szsh",
            "notice": "",
            "all": "",
            None: "",
            "": "",
        }
        return mapping.get(category, category or "")

    async def get_announcements(
        self,
        symbol: str,
        *,
        limit: int = 20,
        category: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[Announcement]:
        stock = normalize_symbol(symbol)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            org_id = await self._get_org_id(stock, session)
            if not org_id:
                return []
            return await self._query_announcements(
                stock,
                session,
                org_id=org_id,
                limit=limit,
                category=category,
                start_date=start_date,
                end_date=end_date,
            )

    async def _query_announcements(
        self,
        stock: AStockSymbol,
        session: aiohttp.ClientSession,
        *,
        org_id: str,
        limit: int,
        category: str | None,
        start_date: str | None,
        end_date: str | None,
    ) -> list[Announcement]:
        url = f"{CNINFO_BASE}/new/hisAnnouncement/query"
        se_date = ""
        if start_date and end_date:
            se_date = f"{start_date}~{end_date}"
        elif start_date:
            se_date = f"{start_date}~{datetime.now().strftime('%Y-%m-%d')}"

        form_data = {
            "pageNum": "1",
            "pageSize": str(max(1, min(limit, 30))),
            "column": self._column(stock),
            "tabName": "fulltext",
            "plate": self._plate(stock),
            "stock": f"{stock.code},{org_id}",
            "searchkey": "",
            "secid": "",
            "category": f"{self._category(category)};" if self._category(category) else "",
            "trade": "",
            "seDate": se_date,
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        try:
            async with session.post(url, headers=self._headers(), data=form_data) as response:
                if response.status != 200:
                    logger.warning("CNINFO query HTTP {} for {}", response.status, stock.canonical)
                    return []
                result = await response.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CNINFO announcement query failed for {}: {}", stock.canonical, exc)
            return []

        announcements = result.get("announcements") or []
        records: list[Announcement] = []
        for item in announcements[:limit]:
            raw = dict(item)
            title = str(item.get("announcementTitle") or "").strip()
            if not title:
                continue
            adjunct_url = str(item.get("adjunctUrl") or "")
            pdf_url = f"{CNINFO_STATIC}/{adjunct_url}" if adjunct_url else None
            publish_time = None
            if adjunct_url and len(adjunct_url) >= 20:
                publish_time = adjunct_url[10:20]
            records.append(
                Announcement(
                    symbol=stock.canonical,
                    code=stock.code,
                    exchange=stock.exchange,
                    source=self.source,
                    title=title,
                    publish_time=publish_time,
                    url=pdf_url,
                    category=category,
                    raw=raw,
                )
            )
        return records
