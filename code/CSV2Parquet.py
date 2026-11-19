from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def csv_to_parquet_chunked(csv_file, parquet_file, chunksize=100_000):
    writer = None

    for chunk in pd.read_csv(csv_file, chunksize=chunksize):
        table = pa.Table.from_pandas(chunk)

        if writer is None:
            writer = pq.ParquetWriter(parquet_file, table.schema)

        writer.write_table(table)

    if writer:
        writer.close()


input_folder = Path(r"C:\Users\daans\Documents\KUL_2026_2027\Intelligent Transport Systems\Project\GitHub ITS\TUMDOT - MUC - Download\Trajectory Data")
output_folder = Path(r"C:\Users\daans\Documents\KUL_2026_2027\Intelligent Transport Systems\Project\GitHub ITS\TUMDOT - MUC - Download\Trajectory Data\Parquet")
output_folder.mkdir(exist_ok=True)

for csv_file in input_folder.glob("*.csv"):
    parquet_file = output_folder / f"{csv_file.stem}.parquet"
    csv_to_parquet_chunked(csv_file, parquet_file)
    print(f"Converted {csv_file.name}")