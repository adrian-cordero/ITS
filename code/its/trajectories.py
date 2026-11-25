"""Load TUMDOT-MUC trajectory parts and put them in the plotting CRS."""

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from pyproj import Transformer

from its.config import (
    BICYCLE,
    BICYCLE_COLUMNS,
    BICYCLE_FILE,
    N_PARTS,
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


def add_metric_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Add columns `utm_x`, `utm_y`: the position in METRIC_CRS (UTM 32N, true metres)."""
    df["utm_x"] = UTM_OFFSET_X + df["translation_x"].to_numpy()
    df["utm_y"] = UTM_OFFSET_Y + df["translation_y"].to_numpy()
    return df


def _from_bicycle_file(categories, columns) -> bool:
    """True when the request only needs what BICYCLE_FILE holds."""
    return (categories is not None and set(categories) <= {BICYCLE}
            and columns is not None and set(columns) <= set(BICYCLE_COLUMNS)
            and BICYCLE_FILE.exists())


def load_combined(path, parts=None, categories=None, columns=None) -> pd.DataFrame:
    """
    Rows of a combined file (code/scripts/build_combined.py), sorted by
    timestamp, with `part` and `x`/`y` added.

    parts       only these parts (None: the whole recording)
    categories  only these category codes (None: all in the file)
    columns     only these columns (None: all in the file)
    """
    dataset = ds.dataset(path)
    if columns is not None:
        columns = list(dict.fromkeys(
            [*columns, "timestamp", "category", "track_id",
             "translation_x", "translation_y", "part"]))
        missing = [c for c in columns if c not in dataset.schema.names]
        if missing:
            raise KeyError(f"{path} has no column(s) {missing}: rebuild it with build_combined.py")
    filt = None
    if parts is not None:
        filt = ds.field("part").isin(list(parts))
    if categories is not None:
        f = ds.field("category").isin(list(categories))
        filt = f if filt is None else filt & f
    df = dataset.to_table(columns=columns, filter=filt).to_pandas()
    # same dtypes as the original parts, so results don't depend on the source
    df = df.astype({c: "int64" for c in ("category", "track_id", "interpolated") if c in df})
    return add_plot_coordinates(df)


def load_bicycles(parts=None, columns=None) -> pd.DataFrame:
    """Cyclists from BICYCLE_FILE (see load_combined)."""
    return load_combined(BICYCLE_FILE, parts, columns=columns or list(BICYCLE_COLUMNS))


def load_part(part: int, categories=None, columns=None) -> pd.DataFrame:
    """
    Load one trajectory part, sorted by timestamp, with `x`/`y` added.

    categories  only keep these category codes (see config.CATEGORY_NAMES)
    columns     only read these columns (translation_x/y are always read)

    Cyclist-only requests are read from BICYCLE_FILE when it exists and
    has the columns; everything else from the part's own file.
    """
    if columns is not None:
        columns = list(dict.fromkeys(
            [*columns, "timestamp", "category", "track_id", "translation_x", "translation_y"]
        ))

    if _from_bicycle_file(categories, columns):
        return load_bicycles([part], columns).drop(columns="part")

    df = pd.read_parquet(parquet_path(part), columns=columns)

    if categories is not None:
        df = df[df["category"].isin(categories)]

    df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return add_plot_coordinates(df)


def parse_parts(text) -> list:
    """'16' -> [16], '14-18' -> [14, ..., 18], 'all' -> every part.

    Only one part or a range: the parts are loaded as one timeline, so
    they must follow each other in time."""
    s = str(text).strip().lower()
    if s == "all":
        return list(range(1, N_PARTS + 1))
    try:
        a, _, b = s.partition("-")
        first, last = int(a), int(b or a)
    except ValueError:
        raise ValueError(f"'{text}': give a part (16), a range (14-18) or 'all'") from None
    if not (1 <= first <= N_PARTS and 1 <= last <= N_PARTS):
        raise ValueError(f"'{text}': parts go from 1 to {N_PARTS}")
    if first > last:
        raise ValueError(f"'{text}': write the range from low to high ({last}-{first})")
    return list(range(first, last + 1))


def parts_label(parts) -> str:
    """File-name stem of a part selection: part16, part14-18 or all."""
    parts = list(parts)
    if parts == list(range(1, N_PARTS + 1)):
        return "all"
    return f"part{parts[0]}" if len(parts) == 1 else f"part{parts[0]}-{parts[-1]}"


def load_parts(parts, categories=None, columns=None) -> pd.DataFrame:
    """
    Several consecutive parts as one timeline (see load_part), with a
    `part` column. Tracks that carry on from one part into the next stay
    one track, so events across a part boundary are found too.
    """
    parts = list(parts)
    if columns is not None:
        columns = list(dict.fromkeys(
            [*columns, "timestamp", "category", "track_id", "translation_x", "translation_y"]))
    if _from_bicycle_file(categories, columns):
        return load_bicycles(parts, columns)
    frames = [load_part(p, categories, columns).assign(part=p) for p in parts]
    return pd.concat(frames, ignore_index=True)       # parts follow each other in time


def part_of(df: pd.DataFrame, times):
    """The part each time falls in, from the `part` column of df (load_parts).
    A time between two parts (e.g. an interpolated crossing) counts as the earlier one."""
    starts = df.groupby("part")["timestamp"].min().sort_values()
    i = np.searchsorted(starts.to_numpy(), np.asarray(times, float), side="right") - 1
    return starts.index.to_numpy()[np.clip(i, 0, len(starts) - 1)]


def frame_timestamps(part: int):
    """Every timestamp of a part, also frames without cyclists (sorted, unique)."""
    ts = pq.read_table(parquet_path(part), columns=["timestamp"])["timestamp"].to_numpy()
    return pd.unique(ts)


def tracks(df: pd.DataFrame) -> dict:
    """{track_id: that track's rows, sorted by timestamp}."""
    return {
        tid: grp.sort_values("timestamp", kind="stable")
        for tid, grp in df.groupby("track_id")
    }


def counts_per_time(df: pd.DataFrame) -> pd.DataFrame:
    """Number of road users per timestamp (rows) and category (columns)."""
    return df.groupby(["timestamp", "category"]).size().unstack(fill_value=0)
