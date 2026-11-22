# ITS

Course project for Intelligent Transport Systems (KU Leuven, 2026–2027). It analyses road-user trajectories from the **TUMDOT-MUC** dataset, recorded at the TEMPUS test site on Rheinstraße in Munich. The goal is to measure cyclist queue behaviour at the intersection: jam density and queue discharge rate.

## Repository layout

```
ITS/
├── data/
│   ├── parquet/              Trajectories: tumdot_muc_part_1 … _22.parquet
│   └── maps/                 Rheinstrasse_osm.osm (base map), waiting/merge areas (.gpkg), QGIS projects
├── code/
│   ├── its/                  Shared library. Importing it never opens a window or loads data.
│   │   ├── config.py         Paths, coordinate systems, categories, which map layers exist, stop/exit lines
│   │   ├── trajectories.py   load_part(), tracks(), counts_per_time()
│   │   ├── maps.py           load_basemap(), load_project_layers()
│   │   ├── analysis/
│   │   │   ├── crossings.py  Line crossings, discharge events, queue size over time
│   │   │   └── queues.py     Jam density, discharge rate
│   │   └── viz/
│   │       ├── styles.py     All colours and line styles
│   │       ├── basemap.py    Draw the map and project layers
│   │       ├── frames.py     Precompute per-timestamp frames
│   │       ├── player.py     AnimationPlayer: dots, slider, play button, hover
│   │       ├── count_graph.py, legends.py, static.py
│   └── scripts/              What you run (see Usage)
├── results/                  Output of run_queue_analysis.py
└── requirements.txt
```

**Where to change what:**
- Colours and styles go in `viz/styles.py`.
- New map layers (drawn in QGIS) are registered in `PROJECT_LAYERS` in `config.py`.
- Analysis goes in `its/analysis/`, as plain functions without plotting.
- Anything that should change with the animation frame is a callback: `player.on_frame(fn)`.

## Data

Each Parquet file holds one part of the TUMDOT-MUC trajectory export (about 500k rows each). `load_part()` adds `x`/`y` columns: the position in Web Mercator (EPSG:3857), which is what all maps and plots use.

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

Web Mercator distorts sizes: at Munich's latitude, lengths are about 1.5× and areas about 2.2× their real value. Use `translation_x/y` (UTM, in metres) for distances, speeds and areas.

The map layers are edited in QGIS (`zone_delimitations.qgz`). `data/maps/` holds a shared snapshot. If you edit the layers in your own folder, point `MAPS_DIR` there (see Setup) and copy the files into `data/maps/` when teammates should get them.

## Setup

Use a virtual environment, so the project's packages don't clash with other Python installs. The shapely version in particular must match numpy (see `requirements.txt`). Run these commands from the repo root.

**1. Create it** (once):

```bash
python -m venv .venv
```

**2. Activate it** (every time you open a new terminal):

| Shell | Command |
|---|---|
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows cmd | `.venv\Scripts\activate.bat` |
| Linux / macOS / WSL | `source .venv/bin/activate` |

Your prompt now starts with `(.venv)`. If PowerShell refuses to run the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.

**3. Install the packages** (once, and again when `requirements.txt` changes):

```bash
pip install -r requirements.txt
```

In VS Code, pick the environment with *Python: Select Interpreter* → `.venv`, so the Run button uses it too. Type `deactivate` to leave the environment.

### Data paths

By default everything is read from the repo's `data/` folder.

To read map layers (or Parquet files, or a different base map) from a folder on your own disk, copy `code/its/local_settings.example.py` to `code/its/local_settings.py` and set the paths in it:

```python
MAPS_DIR = r"C:\Users\<you>\OneDrive\...\project\maps"
```

`local_settings.py` is git-ignored, so everyone keeps their own. Windows paths also work under WSL. Environment variables (`ITS_MAPS_DIR`, `ITS_PARQUET_DIR`, `ITS_BASEMAP`) override the file. `animate.py` prints which maps folder it is using.

## Usage

Run the scripts from the repo root (or with the IDE's Run button). Add `--help` to any script to see all its options.

```bash
# Animation. Default: part 16, pedestrians + cyclists, waiting/merge areas, count graph
python code/scripts/animate.py
python code/scripts/animate.py --part 3 --categories 1 3 --layers waiting_areas system
python code/scripts/animate.py --no-graph --satellite
python code/scripts/animate.py --save frame.png --frame 500     # still image, no window

# Static plot of all trajectories in a part
python code/scripts/plot_trajectories.py --part 1 --categories 3 --layers waiting_areas

# Queue analysis: writes results/events.csv and results/event_series.csv
# (needs STOP_EXIT_PAIRS in config.py)
python code/scripts/run_queue_analysis.py --parts 16

# Rebuild the Parquet files from the original CSVs
python code/scripts/csv_to_parquet.py "path/to/Trajectory Data"
```

In the animation window, use the time slider and the Play/Pause button. Hover over a dot to see its track ID and category.

## Status

- [x] Convert the data to Parquet
- [x] Visualise and animate trajectories on the site map, with waiting and merge areas
- [x] Detect stop-line → exit-line events per cyclist (`its/analysis/crossings.py`)
- [ ] Define the stop/exit lines (`STOP_EXIT_PAIRS` in `config.py`)
- [ ] Count only cyclists inside the waiting area per event (the `zone` argument of `event_time_series`)
- [ ] Jam density and discharge rate per event
