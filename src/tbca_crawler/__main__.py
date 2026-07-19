
import logging
from pathlib import Path

from .client import TBCAClient
from .crawler import TBCACrawler
from .exporters import export_json, export_markdown
from .constants import FoodGroup, FoodType


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


if __name__ == "__main__":
    configure_logging()

    with TBCAClient() as client:
        crawler = TBCACrawler(client)

        # # Busca simples (sem detalhes nutricionais)
        # items = crawler.search(food_type=FoodType.IN_NATURA)

        # # Crawl completo (com detalhes)
        # items = crawler.crawl(group=FoodGroup.SUGARS_AND_SWEETS, load_details=True)

        # Crawl de todos os grupos
        items = crawler.crawl_all_groups()

    file_path = Path('src/data')
    export_markdown(items, file_path / '_Alimentos.md')

    