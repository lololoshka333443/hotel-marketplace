"""Amenity catalog — the one list of conveniences a property may offer.

The DB stores an array of keys; the labels live here so the partner cabinet
and the guest catalog can never show two names for the same key. Adding an
amenity is a code change here (and a translation when i18n lands); the column
itself is free-form, so nothing in the schema has to move.

Keys are stable: the frontend keeps them, and a removed entry degrades to its
label rather than a crash.
"""

from __future__ import annotations

# key -> (Russian label, lucide-react icon name).
# The icon name is a string, not an imported component, because this module is
# the backend's source of truth too; the frontend maps it to the component.
AMENITY_CATALOG: dict[str, tuple[str, str]] = {
    "wifi": ("Wi-Fi", "wifi"),
    "parking": ("Парковка", "car"),
    "pool": ("Бассейн", "waves"),
    "breakfast": ("Завтрак", "coffee"),
    "kitchen": ("Кухня", "utensils"),
    "washer": ("Стиральная машина", "shirt"),
    "conditioner": ("Кондиционер", "snowflake"),
    "heating": ("Отопление", "flame"),
    "tv": ("Телевизор", "tv"),
    "balcony": ("Балкон", "building"),
    "sea_view": ("Вид на море", "sailboat"),
    "pets": ("Можно с животными", "paw-print"),
    "smoking": ("Можно курить", "cigarette"),
    "family": ("Семейный", "baby"),
    "accessibility": ("Доступность", "accessibility"),
    "gym": ("Спортзал", "dumbbell"),
    "spa": ("Спа", "flower-2"),
    "transfer": ("Трансфер", "bus"),
}

ALL_AMENITY_KEYS = tuple(AMENITY_CATALOG)


def label_for(key: str) -> str:
    """The Russian label, or the key itself if the catalog lost the entry."""
    return AMENITY_CATALOG.get(key, (key, ""))[0]


def normalise(amenities: object) -> list[str]:
    """Coerce any client input to a de-duplicated list of known keys.

    Unknown keys are dropped: a typo would otherwise surface to the guest as
    its own key. Order follows first appearance, so the partner's order is
    what the guest sees.
    """
    if not isinstance(amenities, (list, tuple)):
        return []
    seen: dict[str, None] = {}
    for item in amenities:
        if isinstance(item, str) and item in AMENITY_CATALOG:
            seen.setdefault(item, None)
    return list(seen)
