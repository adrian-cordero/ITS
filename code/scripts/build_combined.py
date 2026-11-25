"""
Combine all trajectory parts into one Parquet file: sorted by time, with
a `part` column, keeping only the road-user categories and columns you
choose. The original part files are read, never changed.

    python code/scripts/build_combined.py                         # cyclists, BICYCLE_COLUMNS
    python code/scripts/build_combined.py --categories 3 8        # cyclists + scooters
    python code/scripts/build_combined.py --add-columns dimension_x dimension_y
    python code/scripts/build_combined.py --categories all --columns all
    python code/scripts/build_combined.py --list                  # categories and columns

Without --output the file goes into PARQUET_DIR, named after the
categories (tumdot_muc_bicycles.parquet, tumdot_muc_car_bicycle.parquet,
...), with _<N>cols added when the columns aren't the default ones. The
defaults rebuild BICYCLE_FILE, the file load_part() reads cyclists from.

An existing file is never replaced unless you pass --overwrite.
The chosen categories and columns are stored in the file's metadata.
"""

import argparse
import json
from pathlib import Path

import _bootstrap  # noqa: F401
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from its.config import (BICYCLE, BICYCLE_COLUMNS, BICYCLE_FILE, CATEGORY_NAMES, N_PARTS,
                        PARQUET_DIR)
from its.trajectories import parquet_path

# Compact integer types; the floats stay float64 (lossless, and float32
# compresses no smaller).
_SMALL_TYPES = {"category": pa.int8(), "track_id": pa.int32(), "interpolated": pa.int8()}

# Always kept: the code can't use a file without them.
_REQUIRED = ("timestamp", "category", "track_id", "translation_x", "translation_y")

METADATA_KEY = b"its_combined"


def available_columns():
    return pq.read_schema(parquet_path(1)).names


def default_output(categories, columns):
    if sorted(categories) == [BICYCLE] and list(columns) == list(BICYCLE_COLUMNS):
        return BICYCLE_FILE
    if sorted(categories) == sorted(CATEGORY_NAMES):
        name = "all"
    else:
        names = [CATEGORY_NAMES[c].lower() for c in sorted(categories)]
        name = names[0] + "s" if len(names) == 1 else "_".join(names)
    if list(columns) != list(BICYCLE_COLUMNS):
        name += f"_{len(columns)}cols"
    return PARQUET_DIR / f"tumdot_muc_{name}.parquet"


def build(output: Path, categories, columns):
    tmp = output.with_suffix(".tmp")
    meta = {METADATA_KEY: json.dumps({"categories": sorted(categories),
                                      "columns": list(columns)}).encode()}
    schema = writer = None
    n_rows = 0
    try:
        for part in range(1, N_PARTS + 1):     # numeric order = time order
            t = pq.read_table(parquet_path(part), columns=list(columns))
            t = t.filter(pc.is_in(t["category"], pa.array(sorted(categories), t["category"].type)))
            if t.num_rows and pc.max(t["track_id"]).as_py() >= 2**31:
                raise SystemExit(f"part {part}: track_id too large for int32")
            t = t.append_column("part", pa.array(np.full(t.num_rows, part, dtype="int8")))
            if schema is None:
                schema = pa.schema([pa.field(f.name, _SMALL_TYPES.get(f.name, f.type))
                                    for f in t.schema], metadata=meta)
                writer = pq.ParquetWriter(tmp, schema, compression="zstd", compression_level=9)
            writer.write_table(t.cast(schema), row_group_size=250_000)
            n_rows += t.num_rows
            print(f"part {part}: {t.num_rows} rows")
    except BaseException:
        if writer is not None:
            writer.close()
            writer = None
        tmp.unlink(missing_ok=True)
        raise
    finally:
        if writer is not None:
            writer.close()
    tmp.replace(output)                         # only replace the target when complete
    return n_rows


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--categories", nargs="+", default=[str(BICYCLE)], metavar="CODE",
                   help="category codes to keep, or 'all' (default 3: cyclists; see --list)")
    p.add_argument("--columns", nargs="+", metavar="COL",
                   help="columns to keep, or 'all' (default: BICYCLE_COLUMNS in config.py); "
                        f"{', '.join(_REQUIRED)} are always kept")
    p.add_argument("--add-columns", nargs="+", default=[], metavar="COL",
                   help="columns to keep on top of --columns, e.g. dimension_x acceleration_x")
    p.add_argument("--output", type=Path, help="file to write (default: named after the choice)")
    p.add_argument("--overwrite", action="store_true", help="replace the output file if it exists")
    p.add_argument("--list", action="store_true", help="show the categories and columns, then stop")
    args = p.parse_args()

    columns_all = available_columns()
    if args.list:
        print("Categories:", ", ".join(f"{c} {n}" for c, n in CATEGORY_NAMES.items()))
        print("Columns:   ", ", ".join(columns_all))
        print("Default columns:", ", ".join(BICYCLE_COLUMNS))
        return

    if [c.lower() for c in args.categories] == ["all"]:
        categories = sorted(CATEGORY_NAMES)
    else:
        try:
            categories = sorted({int(c) for c in args.categories})
        except ValueError:
            p.error("--categories takes category codes (see --list) or 'all'")
        unknown = [c for c in categories if c not in CATEGORY_NAMES]
        if unknown:
            p.error(f"unknown category code(s) {unknown}; see --list")

    if args.columns and [c.lower() for c in args.columns] == ["all"]:
        chosen = columns_all
    else:
        chosen = [*_REQUIRED, *(args.columns or BICYCLE_COLUMNS), *args.add_columns]
    unknown = [c for c in chosen if c not in columns_all]
    if unknown:
        p.error(f"unknown column(s) {unknown}; see --list")
    # file order, so the same choice always gives the same name and layout
    columns = [c for c in columns_all if c in set(chosen)]
    if set(columns) == set(BICYCLE_COLUMNS):
        columns = list(BICYCLE_COLUMNS)

    output = args.output or default_output(categories, columns)
    if output.exists() and not args.overwrite:
        raise SystemExit(f"{output} already exists; pass --overwrite to replace it, "
                         "or --output to write somewhere else")

    print(f"Categories: {', '.join(CATEGORY_NAMES[c] for c in categories)}")
    print(f"Columns:    {', '.join(columns)} (+ part)")
    output.parent.mkdir(parents=True, exist_ok=True)
    n = build(output, categories, columns)
    print(f"Wrote {output}: {n} rows, {output.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
