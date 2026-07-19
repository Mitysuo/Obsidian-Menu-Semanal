from __future__ import annotations

from dataclasses import replace

from urllib.parse import parse_qs, urljoin, urlparse
from bs4 import BeautifulSoup, NavigableString, Tag

from .models import FoodItem, Nutrient


class TBCAParser:
    def parse_search_results(
        self,
        html: str,
        base_url: str,
    ) -> list:
        soup = BeautifulSoup(html, "lxml")

        table = soup.select_one("table.table.table-striped")

        if table is None:
            return []

        items: list[FoodItem] = []

        for row in table.select("tr"):
            cells = row.find_all("td", recursive=False)

            if len(cells) < 4:
                continue

            link = cells[0].find("a", href=True)

            detail_url = ""
            if isinstance(link, Tag):
                href = link.get("href")

                if isinstance(href, str):
                    detail_url = self._join_url(base_url, href)

            item = FoodItem(
                code=cells[0].get_text(" ", strip=True),
                name=cells[1].get_text(" ", strip=True),
                scientific_name=cells[2].get_text(" ", strip=True),
                group=cells[3].get_text(" ", strip=True),
                brand=(
                    cells[4].get_text(" ", strip=True)
                    if len(cells) >= 5
                    else ""
                ),
                detail_url=detail_url,
            )

            items.append(item)

        return items

    def parse_total_pages(self, html: str) -> int:
        soup = BeautifulSoup(html, "lxml")
        pagination = soup.select_one("ul.pagination")

        if pagination is None:
            return 1

        page_numbers: list[int] = []

        for link in pagination.select("a"):
            text = link.get_text(strip=True)

            if text.isdigit():
                page_numbers.append(int(text))

        return max(page_numbers, default=1)

    def parse_food_detail(
        self,
        html: str,
        search_item: FoodItem,
    ) -> FoodItem:
        soup = BeautifulSoup(html, "lxml")

        item = replace(
            search_item,
            nutrients=[],
        )

        overview_fields = self._parse_overview(soup)

        item.code = overview_fields.get("Código", item.code)
        item.group = overview_fields.get("Grupo", item.group)
        item.food_type = overview_fields.get(
            "Tipo de Alimento",
            item.food_type,
        )
        item.scientific_name = overview_fields.get(
            "Nome Científico",
            item.scientific_name,
        )
        item.brand = overview_fields.get("Marca", item.brand)
        item.description_pt = overview_fields.get(
            "Descrição",
            item.description_pt,
        )

        item.nutrients = self._parse_nutrients(soup)

        return item

    def _parse_overview(
        self,
        soup: BeautifulSoup,
    ) -> dict[str, str]:
        overview = soup.find(id="overview")

        if not isinstance(overview, Tag):
            return {}

        fields: dict[str, str] = {}

        for strong in overview.find_all("strong"):
            label = strong.get_text(" ", strip=True).rstrip(":").strip()

            if not label:
                continue

            value_parts: list[str] = []

            for sibling in strong.next_siblings:
                if isinstance(sibling, Tag) and sibling.name == "br":
                    break

                if isinstance(sibling, NavigableString):
                    value_parts.append(str(sibling))
                    continue

                if isinstance(sibling, Tag):
                    value_parts.append(
                        sibling.get_text(" ", strip=True)
                    )

            value = " ".join(value_parts)
            value = self._normalize_text(value)

            if value:
                fields[label] = value

        return fields

    def _parse_nutrients(
        self,
        soup: BeautifulSoup,
    ) -> list: 
        table = soup.select_one("table#tabela1")

        if table is None:
            return []

        nutrients: list[Nutrient] = []

        for row in table.select("tbody tr"):
            columns = row.find_all("td", recursive=False)

            if len(columns) < 3:
                continue

            component = columns[0].get_text(" ", strip=True)
            unit = columns[1].get_text(" ", strip=True)
            value_per_100g = columns[2].get_text(" ", strip=True)

            if not component:
                continue

            nutrients.append(
                Nutrient(
                    name=component,
                    unit=unit,
                    value_per_100g=value_per_100g,
                )
            )

        return nutrients
    
    
    def parse_next_page_url(
        self,
        html: str,
        current_url: str,
    ) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        pagination = soup.select_one(
            "#block_2.pagination"
        )

        if pagination is None:
            return None

        for link in pagination.find_all("a", href=True):
            link_text = link.get_text(
                " ",
                strip=True,
            ).lower()

            if "próxima" not in link_text:
                continue

            href = link.get("href")

            if not isinstance(href, str):
                continue

            href = href.strip()

            if not href or href == "#":
                continue

            return urljoin(current_url, href)

        return None

    @staticmethod
    def parse_page_number_from_url(
        url: str,
    ) -> int | None:
        query = parse_qs(urlparse(url).query)
        page_values = query.get("pagina")

        if not page_values:
            return None

        try:
            return int(page_values[0])
        except (TypeError, ValueError):
            return None


    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.replace("\xa0", " ").split())

    @staticmethod
    def _join_url(base_url: str, target: str) -> str:
        from urllib.parse import urljoin

        return urljoin(base_url, target)