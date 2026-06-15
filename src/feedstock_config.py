"""Feedstock categories and crop lists shared by the input form and pipelines.

`DICT_RENAME` is the Italy feedstock grouping (category -> source columns) used by
the CR / feedstock-availability notebooks. Its keys are the user-facing feedstock
options. "Crops" is handled separately per country:
  - Spain: pick specific crops from `crop_mapping_spain.csv` (Product_name).
  - Italy: a single "Seminativi" (arable land) category, no per-crop pick.
"""

from __future__ import annotations

import functools

import pandas as pd

# Italy feedstock grouping: category -> underlying (ktn) source columns.
DICT_RENAME = {
    "Cow Manure": [
        "cattle under one year old (ktn)",
        "Cattle from one year to less than two years old: males (ktn)",
        "Cattle from one year to less than two years old: females (ktn)",
        "cattle two years old and older (ktn)",
    ],
    "Cow Slurry": [
        "Cattle two years and older: dairy cows (ktn)",
        "total buffaloes (ktn)",
    ],
    "Pig Slurry": [
        "pigs weighing less than 20 kg (ktn)",
        "pigs from 20 kg to less than 50 kg (ktn)",
        "fattening pigs of 50 kg and more (ktn)",
        "breeding pigs of 50 kg and more (ktn)",
    ],
    "Poultry Broiler Manure": [
        "chickens for meat (ktn)",
        "turkeys (ktn)",
        "pharaoh (ktn)",
        "geese (ktn)",
        "other poultry (ktn)",
    ],
    "Poultry Laying Manure": [
        "egg-laying hens (ktn)",
    ],
    "Sheep and Goat Manure": [
        "sheep (ktn)",
        "goats (ktn)",
    ],
}

# Feedstock-availability selector options (aggregation categories from dict_rename).
# Crops are NOT here — crops belong to the NR / hectares (land) side, not the diet.
FEEDSTOCK_KEYS = list(DICT_RENAME.keys())

# CR diet vocabulary (plant + competitor diets), matching the notebook `sites` dict.
# Values are inclusion flags (1 = in the diet), as in the notebooks.
DIET_KEYS = [
    "Cow Slurry",
    "Cow Manure",
    "Pig Manure",
    "Pig Slurry",
    "Poultry Manure",
    "Poultry Broiler Manure",
    "Poultry Laying Manure",
    "Sheep and Goat Manure",
]

# Italy crops are a single arable-land category.
ITALY_CROP_LABEL = "Seminativi"

_CROP_MAPPING_SPAIN = "assets/crop_mapping_spain.csv"


@functools.lru_cache(maxsize=1)
def load_spain_crops() -> tuple:
    """Sorted, de-duplicated crop names from crop_mapping_spain.csv (Product_name).

    Returns a tuple so the result is hashable / cacheable. Excludes the
    'PRODUCTO DESCONOCIDO' (unknown) placeholder.
    """
    try:
        df = pd.read_csv(_CROP_MAPPING_SPAIN, usecols=["Product_name"])
    except Exception:
        return tuple()
    names = (
        df["Product_name"]
        .dropna()
        .astype(str)
        .str.strip()
    )
    names = [n for n in names.unique() if n and n.upper() != "PRODUCTO DESCONOCIDO"]
    return tuple(sorted(names))
