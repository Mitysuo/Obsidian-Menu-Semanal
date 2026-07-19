from __future__ import annotations

from dataclasses import dataclass, field

from .constants import (
    FoodGroup,
    FoodType,
)


@dataclass(slots=True)
class Nutrient:
    name: str
    unit: str = ""
    value_per_100g: str = ""

    @property
    def display_name(self) -> str:
        if self.unit:
            return f"{self.name} ({self.unit})"

        return self.name


@dataclass(slots=True)
class FoodItem:
    code: str = ""
    name: str = ""
    scientific_name: str = ""
    group: FoodGroup | None = None
    food_type: FoodType | None = None
    brand: str = ""
    description_pt: str = ""
    detail_url: str = ""
    nutrients: list[Nutrient] = field(default_factory=list)