# ITS

Course project for Intelligent Transport Systems (KU Leuven, 2026–2027). It analyses road-user trajectories from the **TUMDOT-MUC** dataset, recorded at the TEMPUS test site on Rheinstraße in Munich. The goal is to measure cyclist queue behaviour at the intersection: jam density and queue discharge rate.

## Repository layout

```
ITS/
├── Parquet/            Trajectory data, split into 22 Parquet files (tumdot_muc_part_1 … _22)
├── code/
│   ├── CSV2Parquet.py                    Converts the original TUMDOT CSV files to Parquet, in chunks
│   ├── Main.py                           Merges the CSVs, plus a pseudocode draft of the queue-discharge analysis
│   ├── Visualization.py                  Static plot of every trajectory on top of the KML map
│   ├── Visualization_animation.py        Animated playback (v1)
│   ├── Visualization_animation_V2.py     Animated playback in Web Mercator over an OSM-derived map (optional satellite basemap)
│   ├── Visualization_animation_V3.py     Fastest version: transforms, colours and frames are computed once up front
│   └── Tempus - Muenchen Rheinstrasse.qgz   QGIS project for the site
└── paper/              LaTeX report (main file: docs/main.tex, body: content/body.tex)
```

## Data

Each Parquet file holds one part of the TUMDOT-MUC trajectory export. Part 1, for example, has about 500k rows. The columns are:

| Column | Meaning |
|---|---|
| `timestamp` | Time in seconds |
| `track_id` | ID of the road user |
| `category` | 1 car, 2 pedestrian, 3 bicycle, 4 trailer, 5 motorcycle, 6 truck, 7 bus, 8 scooter, 9 streetcar |
| `translation_x/y/z` | Position, as a local offset in UTM32N (offset x = 692009.0, y = 5338095.0) |
| `dimension_x/y/z` | Size of the bounding box |
| `rotation_x/y/z` | Orientation |
| `velocity_x/y/z`, `acceleration_x/y/z` | Motion |
| `interpolated` | 1 if the point was interpolated |

The map files (`2023-03-22_1477_TEMPUS_Rheinstrasse_ODR.kml` and `osm_converted.kml`) come with the TUMDOT-MUC download under `Map Data/` and are **not** in this repository.

## Setup

Python 3 with:

```bash
pip install pandas pyarrow geopandas fiona matplotlib mplcursors pyproj numpy contextily
```

`contextily` is used only by V2, for the satellite basemap, which is commented out by default.

## Usage

The scripts currently use hard-coded Windows paths (`C:/Users/daans/...`). Before you run a script, point `kml_file` and `parquet_file` at your local copies. For the trajectories, that can be this repo's `Parquet/` folder.

To pick which part to load, set `file_number` at the top of the animation scripts. Then run:

```bash
python code/Visualization_animation_V3.py
```

The animation window has a time slider and a Play/Pause button. Hover over a point to see its track ID and category.

To rebuild the Parquet files from the original CSVs, set `input_folder` and `output_folder` in `CSV2Parquet.py` and run it.

## Status

- [x] Convert the data to Parquet
- [x] Visualise and animate trajectories on the site map
- [ ] Queue discharge rate and jam density analysis (pseudocode in `Main.py`)
- [ ] Report (`paper/`, section skeleton only)
