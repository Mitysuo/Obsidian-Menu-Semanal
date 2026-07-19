from __future__ import annotations

import csv
import json
import logging
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from .models import FoodItem


logger = logging.getLogger(__name__)


def export_csv(
    items: Sequence[FoodItem],
    filepath: str | Path,
) -> None:
    if not items:
        logger.warning("Nenhum alimento disponível para exportação CSV.")
        return

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    nutrient_columns = _get_all_nutrient_columns(items)

    fieldnames = [
        "codigo",
        "nome",
        "nome_cientifico",
        "grupo",
        "tipo",
        "marca",
        "descricao",
        "url_detalhes",
        *nutrient_columns,
    ]

    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()

        for item in items:
            row: dict[str, str] = {
                "codigo": item.code,
                "nome": item.name,
                "nome_cientifico": item.scientific_name,
                "grupo": item.group,
                "tipo": item.food_type,
                "marca": item.brand,
                "descricao": item.description_pt,
                "url_detalhes": item.detail_url,
            }

            nutrient_values = {
                nutrient.display_name: nutrient.value_per_100g
                for nutrient in item.nutrients
            }

            for column in nutrient_columns:
                row[column] = nutrient_values.get(column, "")

            writer.writerow(
                {
                    key: _sanitize_csv_value(value)
                    for key, value in row.items()
                }
            )

    logger.info("Arquivo CSV exportado para %s", path)


def export_json(
    items: Sequence[FoodItem],
    filepath: str | Path,
) -> None:
    if not items:
        logger.warning("Nenhum alimento disponível para exportação JSON.")
        return

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = [asdict(item) for item in items]

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )

    logger.info("Arquivo JSON exportado para %s", path)


def export_markdown(
    items: Sequence[FoodItem],
    filepath: str | Path,
) -> None:
    if not items:
        logger.warning(
            "Nenhum alimento disponível para exportação Markdown."
        )
        return

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        "tipo: alimento_db",
        "alimentos:",
    ]

    for item in items:
        lines.extend(
            [
                f"  - nome: {_yaml_value(item.name)}",
                f"    codigo: {_yaml_value(item.code)}",
                f"    grupo: {_yaml_value(item.group)}",
                f"    tipo: {_yaml_value(item.food_type)}",
                f"    marca: {_yaml_value(item.brand)}",
                "    nutrientes:",
            ]
        )

        if not item.nutrients:
            lines.append("      {}")
            continue

        for nutrient in sorted(
            item.nutrients,
            key=lambda value: value.display_name.casefold(),
        ):
            lines.append(
                "      "
                f"{_yaml_key(nutrient.display_name)}: "
                f"{_yaml_value(nutrient.value_per_100g)}"
            )

    lines.extend(
        [
            "---",
            "",
            "# Base de alimentos TBCA",
            "",
            f"Total de alimentos: {len(items)}",
            "",
        ]
    )

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    logger.info(
        "Arquivo Markdown para Obsidian exportado para %s",
        path,
    )

def _get_all_nutrient_columns(
    items: Sequence[FoodItem],
) -> list:
    columns = {
        nutrient.display_name
        for item in items
        for nutrient in item.nutrients
    }

    return sorted(columns, key=str.casefold)


def _sanitize_csv_value(value: str) -> str:
    if not value:
        return value

    stripped_value = value.lstrip()

    if stripped_value.startswith(("=", "+", "@")):
        return "'" + value

    return value

def _yaml_value(value: object) -> str:
    if value is None or value == "":
        return '""'

    return json.dumps(
        str(value),
        ensure_ascii=False,
    )


def _yaml_key(value: object) -> str:
    return json.dumps(
        str(value),
        ensure_ascii=False,
    )
