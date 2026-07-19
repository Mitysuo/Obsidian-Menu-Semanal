from __future__ import annotations

import logging
from collections.abc import Iterator
from urllib.parse import urljoin

import requests

from .client import TBCAClient

from .constants import (
    FOOD_GROUPS,
    FOOD_TYPES,
    SEARCH_ENDPOINT,
    FoodGroup,
    FoodType,
)

from .models import FoodItem
from .parser import TBCAParser


logger = logging.getLogger(__name__)


class TBCACrawler:
    def __init__(
        self,
        client: TBCAClient,
        parser: TBCAParser | None = None,
    ) -> None:
        self.client = client
        self.parser = parser or TBCAParser()

    def search(
        self,
        product: str = "",
        group: FoodGroup | None = None,
        food_type: FoodType | None = None,
    ) -> list:
        html, current_url = self._request_first_page(
            product=product,
            group=group,
            food_type=food_type,
        )

        return self.parser.parse_search_results(
            html,
            current_url,
        )

    def search_all_pages(
        self,
        product: str = "",
        group: FoodGroup | None = None,
        food_type: FoodType | None = None,
        max_pages: int | None = None,
        max_items: int | None = None,
    ) -> list:
        return list(
            self.iter_search_results(
                product=product,
                group=group,
                food_type=food_type,
                max_pages=max_pages,
                max_items=max_items,
            )
        )

    def iter_search_results(
        self,
        product: str = "",
        group: FoodGroup | None = None,
        food_type: FoodType | None = None,
        max_pages: int | None = None,
        max_items: int | None = None,
    ) -> Iterator:
        self._validate_limit("max_pages", max_pages)
        self._validate_limit("max_items", max_items)

        html, current_url = self._request_first_page(
            product=product,
            group=group,
            food_type=food_type,
        )

        processed_pages = 0
        yielded_items = 0

        visited_urls: set[str] = set()

        while True:
            processed_pages += 1
            visited_urls.add(current_url)

            logger.info(
                "Processando página %d: %s",
                processed_pages,
                current_url,
            )

            page_items = self.parser.parse_search_results(
                html,
                current_url,
            )

            if not page_items:
                logger.warning(
                    "A página %d não retornou alimentos: %s",
                    processed_pages,
                    current_url,
                )

            for item in page_items:
                yield item
                yielded_items += 1

                if (
                    max_items is not None
                    and yielded_items >= max_items
                ):
                    logger.info(
                        "Limite de %d alimentos atingido.",
                        max_items,
                    )
                    return

            if (
                max_pages is not None
                and processed_pages >= max_pages
            ):
                logger.info(
                    "Limite de %d páginas atingido.",
                    max_pages,
                )
                return

            next_url = self.parser.parse_next_page_url(
                html=html,
                current_url=current_url,
            )

            if next_url is None:
                logger.info(
                    "Não existe próxima página. "
                    "Paginação finalizada."
                )
                return

            if next_url in visited_urls:
                logger.warning(
                    "A próxima URL já foi processada. "
                    "Interrompendo para evitar loop: %s",
                    next_url,
                )
                return

            next_page_number = (
                self.parser.parse_page_number_from_url(
                    next_url
                )
            )

            if next_page_number is not None:
                logger.info(
                    "Buscando página %d: %s",
                    next_page_number,
                    next_url,
                )
            else:
                logger.info(
                    "Buscando próxima página: %s",
                    next_url,
                )

            html, current_url = self._request_url(next_url)

    def get_food_detail(
        self,
        item: FoodItem,
    ) -> FoodItem | None:
        if not item.detail_url:
            logger.warning(
                "O alimento %s não possui URL de detalhes.",
                item.code or item.name,
            )
            return None

        response = self.client.get(item.detail_url)

        return self.parser.parse_food_detail(
            response.text,
            item,
        )

    def crawl(
        self,
        product: str = "",
        group: FoodGroup | None = None,
        food_type: FoodType | None = None,
        max_pages: int | None = None,
        max_items: int | None = None,
        load_details: bool = True,
    ) -> list:
        items = self.search_all_pages(
            product=product,
            group=group,
            food_type=food_type,
            max_pages=max_pages,
            max_items=max_items,
        )

        logger.info(
            "Total de alimentos encontrados: %d",
            len(items),
        )

        if not load_details:
            return items

        return self._load_details(items)

    def crawl_all_groups(
        self,
        max_pages_per_group: int | None = None,
        max_items: int | None = None,
        load_details: bool = True,
    ) -> list:
        self._validate_limit(
            "max_pages_per_group",
            max_pages_per_group,
        )
        self._validate_limit("max_items", max_items)

        unique_items: list[FoodItem] = []
        seen_identifiers: set[str] = set()

        for group in FoodGroup:
            group_name = FOOD_GROUPS[group.value]
                                     
            logger.info(
                f"Processando grupo {group.value} - {group_name}")

            for item in self.iter_search_results(
                group=group,
                max_pages=max_pages_per_group,
            ):
                identifier = self._get_item_identifier(item)

                if identifier in seen_identifiers:
                    logger.debug(
                        f"Alimento duplicado ignorado: {identifier}")
                    continue

                seen_identifiers.add(identifier)
                unique_items.append(item)

                if (
                    max_items is not None
                    and len(unique_items) >= max_items
                ):
                    logger.info(
                        "Limite global de %d alimentos atingido.",
                        max_items,
                    )

                    if not load_details:
                        return unique_items

                    return self._load_details(unique_items)

        logger.info(
            "Total de alimentos únicos encontrados: %d",
            len(unique_items),
        )

        if not load_details:
            return unique_items

        return self._load_details(unique_items)

    def _load_details(
        self,
        items: list[FoodItem],
    ) -> list:
        detailed_items: list[FoodItem] = []
        total_items = len(items)

        for index, item in enumerate(items, start=1):
            logger.info(
                "Carregando detalhes [%d/%d]: %s - %s",
                index,
                total_items,
                item.code,
                item.name,
            )

            try:
                detailed_item = self.get_food_detail(item)
            except requests.RequestException as exception:
                logger.warning(
                    "Falha HTTP ao carregar o alimento %s: %s",
                    item.code or item.name,
                    exception,
                )
                detailed_items.append(item)
                continue
            except (
                AttributeError,
                KeyError,
                TypeError,
                ValueError,
            ) as exception:
                logger.exception(
                    "Falha ao interpretar o alimento %s: %s",
                    item.code or item.name,
                    exception,
                )
                detailed_items.append(item)
                continue

            detailed_items.append(detailed_item or item)

        return detailed_items

    def _request_first_page(
        self,
        product: str,
        group: str,
        food_type: str,
    ) -> tuple[str, str]:
        url = urljoin(
            self.client.base_url,
            SEARCH_ENDPOINT,
        )

        form_data = self._build_search_parameters(
            product=product,
            group=group,
            food_type=food_type,
        )

        response = self.client.post(
            url,
            data=form_data,
        )

        return response.text, response.url

    def _request_url(
        self,
        url: str,
    ) -> tuple[str, str]:
        response = self.client.get(url)
        return response.text, response.url

    @staticmethod
    def _build_search_parameters(
        product: str,
        group: FoodGroup | None,
        food_type: FoodType | None,
    ) -> dict[str, str]:
        return {
            "guarda": "tomo1",
            "produto": product,
            "cmb_grupo": group.value if group is not None else "",
            "cmb_tipo_alimento": (
                food_type.value
                if food_type is not None
                else ""
            ),
        }

    @staticmethod
    def _get_item_identifier(
        item: FoodItem,
    ) -> str:
        if item.code:
            return f"code:{item.code}"

        if item.detail_url:
            return f"url:{item.detail_url}"

        return (
            f"name:{item.name}|"
            f"group:{item.group}|"
            f"brand:{item.brand}"
        )

    @staticmethod
    def _validate_limit(
        parameter_name: str,
        value: int | None,
    ) -> None:
        if value is not None and value <= 0:
            raise ValueError(
                f"{parameter_name} deve ser maior "
                "que zero ou None."
            )