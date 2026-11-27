# ITS

Course project for Intelligent Transport Systems (KU Leuven, 2026–2027). It analyses road-user trajectories from the **TUMDOT-MUC** dataset, recorded at the TEMPUS test site on Rheinstraße in Munich. The goal is to measure cyclist queue behaviour at the intersection: jam density and queue discharge rate.

## Repository layout

```
ITS/
├── data/
│   ├── parquet/              Trajectories: tumdot_muc_part_1 … _22.parquet, and tumdot_muc_bicycles.parquet
│   └── maps/                 Rheinstrasse_osm.osm (base map), waiting/merge areas (.gpkg), QGIS projects
├── code/
│   ├── its/                  Shared library. Importing it never opens a window or loads data.
│   │   ├── config.py         Paths, coordinate systems, categories, map layers, event thresholds
│   │   ├── trajectories.py   load_part(), load_parts(), load_bicycles(), frame_timestamps(), counts_per_time()
│   │   ├── maps.py           load_basemap(), load_project_layers()
│   │   ├── crossings.py      Crossing geometry: bands between two waiting areas and their lines
│   │   ├── analysis/         Event detection (see docs/events.md)
│   │   │   ├── occupancy.py    Road users inside each area per timestep, entries and exits
│   │   │   ├── line_passes.py  Road users going over a line, with direction and interpolated time
│   │   │   ├── start_stop.py   Start and stop events, with a snapshot of the waiting area
│   │   │   └── discharge.py    Discharges: a stopped queue released over a crossing's lines
│   │   └── viz/
│   │       ├── styles.py     All colours and line styles
│   │       ├── basemap.py    Draw the map and project layers, frame the view
│   │       ├── crossings.py  Draw crossing lines
│   │       ├── frames.py     Per-timestamp frames as slices of sorted arrays
│   │       ├── player.py     AnimationPlayer: dots, slider, play/speed buttons, hover
│   │       ├── events.py     Crossings in the local frame, shared by the event viewers
│   │       └── count_graph.py, legends.py, static.py, interaction.py
│   └── scripts/              What you run (see Usage)
├── docs/events.md            Which events are detected and how
├── results/
│   ├── occupancy/            Output of detect_occupancy.py
│   └── queue_events/         Output of detect_queue_events.py (read by view_discharges.py)
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

The 22 parts are consecutive 600 s slices of one recording (part 1 starts at −313 s, part 22 ends at 12 881 s), and track IDs carry on across them: a road user near the end of a part usually continues in the next one.

**Bicycle file.** `tumdot_muc_bicycles.parquet` holds the cyclists of all 22 parts in one file (3.2 M rows, 56 MB): sorted by time, with a `part` column, and only the columns in `BICYCLE_COLUMNS` (`config.py`). `load_part()` reads cyclist-only requests from it automatically, and everything else from the part files, which stay the original data. `load_bicycles()` reads several parts, or the whole recording, in one go. To keep another column, add it to `BICYCLE_COLUMNS` and rebuild:

```bash
python code/scripts/build_combined.py
```

The same script makes other combined files, e.g. with more road-user types or columns. Those get their own name, and an existing file is never replaced without `--overwrite`. Read one with `load_combined(path, parts=..., categories=...)`.

```bash
python code/scripts/build_combined.py --list                                   # categories and columns
python code/scripts/build_combined.py --categories 3 8                         # tumdot_muc_bicycle_scooter.parquet
python code/scripts/build_combined.py --add-columns dimension_x dimension_y    # tumdot_muc_bicycles_9cols.parquet
python code/scripts/build_combined.py --categories all --columns all --output some/file.parquet
```

Web Mercator distorts sizes: at Munich's latitude, lengths are about 1.5× and areas about 2.2× their real value. Use `translation_x/y` (UTM, in metres) for distances, speeds and areas.

The map layers are edited in QGIS (`zone_delimitations.qgz`). `data/maps/` holds a shared snapshot. If you edit the layers in your own folder, point `MAPS_DIR` there (see Setup) and copy the files into `data/maps/` when teammates should get them. The crossings are the exception: `define_crossings.py` always saves them in `data/maps/` (`CROSSINGS_DIR`), together with a copy of the waiting-areas file they were picked on, so commit those three files after changing crossings.

## Map layers

Layers are imported from the maps folder: `data/maps/`, or your own folder via `MAPS_DIR` (see *Data paths* under Setup).

```bash
# List the files and layers in the maps folder
python -c "import sys; sys.path.insert(0, 'code'); from its.maps import list_available; print(list_available())"

# Draw specific layers in a script (names come from PROJECT_LAYERS in config.py)
python code/scripts/animate.py --layers waiting_areas merge_areas
```

```python
# In your own code
from its.maps import load_project_layers
layers = load_project_layers(["waiting_areas", "merge_areas"])   # {name: GeoDataFrame}
```

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

Every script with `--part` runs on the whole recording by default; `--part 16` or `--part 14-18` picks one part or a range.

```bash
# Animation. Default: all parts, cyclists only, framed on the crossings + 10 m, count graph
python code/scripts/animate.py
python code/scripts/animate.py --speed 4 --margin 25      # 4x real time; --full = all trajectories
python code/scripts/animate.py --part 3 --categories 1 3 --layers waiting_areas system
python code/scripts/animate.py --no-graph --satellite
python code/scripts/animate.py --save frame.png --frame 500     # still image, no window

# Crossing areas: add/edit/delete crossings, then rebuild with another width without re-picking
python code/scripts/define_crossings.py --width 5
python code/scripts/define_crossings.py --rebuild --width 4
python code/scripts/define_crossings.py --reset              # delete all crossings and start over (asks first)

# Static plot of all trajectories
python code/scripts/plot_trajectories.py --categories 3 --layers waiting_areas

# Occupancy and line passes: cyclists per waiting area per timestep, start/end line passes
python code/scripts/detect_occupancy.py

# Cyclists inside the waiting areas over time (checkboxes pick the areas)
python code/scripts/plot_occupancy.py
python code/scripts/plot_occupancy.py --areas 0 1 4

# Queue events in a crossing's start waiting area: start-line passes ("start"), cyclists
# stopping ("stop") and queues released over the crossing's lines ("discharge")
# (tables + a photo of the area and the whole intersection per event; --view steps through them)
python code/scripts/detect_queue_events.py --view
python code/scripts/detect_queue_events.py --near 5 --stop-speed 0.1 --stop-duration 0.5
python code/scripts/detect_queue_events.py --types discharge --max-lag 90 --lines 4

# Discharge viewer (reads the CSVs above): queue & paths, time–distance, start-line headways
python code/scripts/view_discharges.py
python code/scripts/view_discharges.py --kind all       # also rolling-start discharges

# One part, then only queues of 4+ cyclists
python code/scripts/detect_queue_events.py --part 16
python code/scripts/view_discharges.py --part 16 --min-bikes 4

# Rebuild the Parquet files from the original CSVs, then the bicycle file
python code/scripts/csv_to_parquet.py "path/to/Trajectory Data"
python code/scripts/build_combined.py
```

In the animation window, use the time slider and the Play/Pause button; − / + (buttons or keys) halve and double the speed, left / right step one frame, page up / page down jump a minute. Hover over a dot to see its track ID and category.

### Crossing areas

`define_crossings.py` builds crossings between the polygons of `CROSSING_LAYER` in `config.py` (currently the waiting areas). Each crossing is a band of constant width that runs from a start edge on one area to an end edge on another area:

1. **Pick.** The window shows the areas numbered in orange, and the existing crossings as `#0`, `#1`, and so on. The terminal lists the crossings, followed by a menu:

   | Command | Does |
   |---|---|
   | `a` | Add a crossing. It asks for the start area, the start edge, the end area, the end edge, the number of lines and the width (Enter = default). |
   | `e 2` | Edit crossing #2. The same questions; Enter keeps the value in brackets. |
   | `d 2` | Delete crossing #2, after a yes/no question. |
   | `r 2` | Reverse crossing #2, swapping its start and end. |
   | `n 2 6` | Give crossing #2 its own number of lines (6). `n 2 -` goes back to the default. |
   | `w 2 3.5` | Give crossing #2 its own width (3.5 m). `w 2 -` goes back to the default. |
   | `clear` | Delete all crossings and start again from #0 (asks first). |
   | `q` | Save and quit. |

   Type `c` while adding or editing to cancel. Any number of crossings can start or end at the same area. Every change is saved straight away.

   `clear` (or `--reset` on the command line) first saves the current picks as `data/maps/edge_picks_backups/edge_picks_backup_<date>-<time>.csv` (git-ignored), a new file each time. To undo, copy that file over `edge_picks.csv` and run `define_crossings.py --rebuild`.
2. **Build.** Both edges get length **W**, centred on their original midpoints. W is the crossing's own width if you gave it one (`w <#> <W>`); otherwise it's the default (`--width`, or `CROSSING_WIDTH` in `config.py`). The end edge is turned parallel to the start edge, and the crossing is the four-sided band between them. **L** is the distance between the two edges. The original areas aren't changed.
3. **Save.** The crossings go into `data/maps/crossing_areas.gpkg` (`CROSSINGS_DIR` in `config.py`), which you can open in QGIS. It has two layers: `crossing_areas` (the bands) and `crossing_edges` (the start/end lines). The picks are saved in `data/maps/edge_picks.csv`. If `MAPS_DIR` points elsewhere, the waiting-areas file the crossings were picked on is copied into `data/maps/` too, since picks refer to its polygons by row number. Commit these files so teammates get the same crossings. Use `--rebuild --width 4` to rebuild without picking again. The new default width only changes crossings that don't have their own.

`animate.py` draws each crossing's start and end edge, plus **N** lines in between. The lines split L into N + 1 equal parts, and each line has length W. N is the crossing's own number if you gave it one (`n <#> <N>` in the menu); otherwise it's the default (`CROSSING_LINES` in `config.py`, or `--lines N` on `animate.py`).

Picks are linked to areas by their order in the layer's file. If you delete or reorder areas in QGIS, pick again.

### Several parts at once

`--part` takes one part (`16`), a range (`14-18`) or `all`. A range is detected as one timeline, so a queue that stops in one part and leaves in the next is still one discharge, and a cyclist who is already standing still when a part begins isn't counted as a new stop. The results go to `results/occupancy/<S>_*.csv` and `results/queue_events/<S>_*.csv` with `<S>` = `part16`, `part14-18` or `all`. Event and discharge IDs run over the whole selection, and a `part` column says which part each event (snapshot time) or discharge (release time) falls in. Run the viewer with the same `--part` as the detection.

`--min-bikes N` (or the viewer's "min bikes" box, Enter to apply) only shows discharges with at least N cyclists in the queue (`n_queue >= N`). The default is `DISCHARGE_MIN_BIKES` in `config.py` (1: all). The CSVs always keep every discharge.

## Event naming

How each event is detected is described in [docs/events.md](docs/events.md).

| Term | Meaning |
|---|---|
| crossing | The area/band from a start line to an end line (`crossing_id`). Never an event. |
| line pass | A road user going over a line (`line_passes.py`): +1 forward (start → end), −1 backward |
| line | One of the crossing's N + 2 lines: `line_index` 0 = start, 1 … N in between, N + 1 = end |
| start event | A cyclist's first forward pass of a start line (`type = "start"`) |
| stop event | A cyclist staying below `STOP_SPEED` for `STOP_DURATION` in the start waiting area (`type = "stop"`) |
| reference stop | The latest stop event of the same crossing at or before a start event, at most `DISCHARGE_MAX_LAG` s earlier |
| queue | Cyclists inside the area with speed below `STOP_SPEED` in the reference stop's snapshot (`queue_position` 1 = nearest the start line) |
| discharge | One queue per reference stop. `trigger_kind = "queue"`: triggered by the first matched start event of a queue member (earlier rolling starts in `n_skipped_starts`). `"rolling"`: no queue member has a matched start event, so the first matched start event (a rolling start) triggers it. |
| discharge pass | A queue member's first forward pass of a line after the reference stop |

## Status

- [x] Convert the data to Parquet
- [x] Visualise and animate trajectories on the site map, with waiting and merge areas
- [x] Cyclists per waiting area per timestep, start/end line passes (`detect_occupancy.py`)
- [x] Start, stop and discharge events (`detect_queue_events.py`)
- [ ] Still TBD
