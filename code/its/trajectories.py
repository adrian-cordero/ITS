"""Load TUMDOT-MUC trajectory parts and put them in the plotting CRS."""

import pandas as pd
from pyproj import Transformer

from its.config import (
    PARQUET_DIR,
    PLOT_CRS,
    TRAJECTORY_CRS,
    UTM_OFFSET_X,
    UTM_OFFSET_Y,
)

_transformer = Transformer.from_crs(
    f"EPSG:{TRAJECTORY_CRS}", f"EPSG:{PLOT_CRS}", always_xy=True
)


def parquet_path(part: int):
    return PARQUET_DIR / f"tumdot_muc_part_{part}.parquet"


def add_plot_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Add columns `x`, `y`: the position in PLOT_CRS (EPSG:3857)."""
    df["x"], df["y"] = _transformer.transform(
        UTM_OFFSET_X + df["translation_x"].to_numpy(),
        UTM_OFFSET_Y + df["translation_y"].to_numpy(),
    )
    return df


def load_part(part: int, categories=None, columns=None) -> pd.DataFrame:
    """
    Load one trajectory part, sorted by timestamp, with `x`/`y` added.

    categories  only keep these category codes (see config.CATEGORY_NAMES)
    columns     only read these columns (translation_x/y are always read)
    """
    if columns is not None:
        columns = list(dict.fromkeys(
            [*columns, "timestamp", "category", "track_id", "translation_x", "translation_y"]
        ))

    df = pd.read_parquet(parquet_path(part), columns=columns)

    if categories is not None:
        df = df[df["category"].isin(categories)]

    df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return add_plot_coordinates(df)


def tracks(df: pd.DataFrame) -> dict:
    """{track_id: that track's rows, sorted by timestamp}."""
    return {
        tid: grp.sort_values("timestamp", kind="stable")
        for tid, grp in df.groupby("track_id")
    }


def counts_per_time(df: pd.DataFrame) -> pd.DataFrame:
    """Number of road users per timestamp (rows) and category (columns)."""
    return df.groupby(["timestamp", "category"]).size().unstack(fill_value=0)
