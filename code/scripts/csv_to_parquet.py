"""
Convert the original TUMDOT-MUC CSV files to Parquet, in chunks so large
files don't need to fit in memory.

    python code/scripts/csv_to_parquet.py "path/to/Trajectory Data"
    python code/scripts/csv_to_parquet.py "path/to/Trajectory Data" --output some/folder
"""

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from its.config import PARQUET_DIR


def csv_to_parquet_chunked(csv_file, parquet_file, chunksize=100_000):
    writer = None
    try:
        for chunk in pd.read_csv(csv_file, chunksize=chunksize):
            table = pa.Table.from_pandas(chunk)
            if writer is None:
                writer = pq.ParquetWriter(parquet_file, table.schema)
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input_folder", type=Path, help="folder with the .csv files")
    p.add_argument("--output", type=Path, default=PARQUET_DIR,
                   help=f"where to write .parquet files (default {PARQUET_DIR})")
    args = p.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    csv_files = sorted(args.input_folder.glob("*.csv"))
    if not csv_files:
        raise SystemExit(f"No .csv files in {args.input_folder}")

    for csv_file in csv_files:
        csv_to_parquet_chunked(csv_file, args.output / f"{csv_file.stem}.parquet")
        print(f"Converted {csv_file.name}")


if __name__ == "__main__":
    main()
