# Detected events

Two scripts detect events. Both run on the whole recording by default
(`--part 16` or `--part 14-18` for one part or a range). The parts are
loaded as one timeline, so a cyclist crossing a part boundary stays one
track. Thresholds live in `code/its/config.py`.

| Script | Events | Code | Output |
|---|---|---|---|
| `detect_occupancy.py` | occupancy, line passes | `analysis/occupancy.py`, `analysis/line_passes.py` | `results/occupancy/` |
| `detect_queue_events.py` | start, stop, discharge | `analysis/start_stop.py`, `analysis/discharge.py` | `results/queue_events/` |

`<P>` in the file names below is `all`, `part16` or `part14-18`.

Words used throughout:

- **waiting area**: a polygon in the waiting-areas layer (`PROJECT_LAYERS["waiting_areas"]`).
- **crossing**: the band from a start edge on one waiting area to an end edge on
  another, drawn with `define_crossings.py`. It has a start line, an end line
  and N lines in between. A crossing is a place, never an event.
- **line pass**: a road user going over one of those lines.

## 1. Occupancy (`detect_occupancy.py`)

A cyclist is *inside* a waiting area when its centre point is inside the
polygon. Each cyclist enters an area at most once and leaves at most once:
its stay runs from its first to its last timestep inside. If its point
wobbles over the edge during the stay, it still counts as inside.

- `<P>_occupancy.csv`: cyclists inside each area (`area_0`, `area_1`, …)
  and in any area (`total`) at every timestep, including empty ones.
- `plot_occupancy.py` plots this and lists entries and exits per area.

## 2. Line passes (`detect_occupancy.py`)

A line pass is a step between two consecutive positions of one track that
intersects a crossing's start or end line. Its direction is +1 going
start → end and −1 the other way. Its time is interpolated between the two
timesteps.

- `<P>_line_passes.csv`: every pass (crossing_id, line, track_id, time,
  direction, x, y).
- `<P>_crossing_summary.csv`: per crossing, the distinct cyclists passing
  each line forward and backward, and how many passed both lines forward.

## 3. Start event (`detect_queue_events.py`, type `start`)

A cyclist's first forward pass of a crossing's start line (one per cyclist
per line). **Snapshot:** the cyclist's last timestep before the line.

## 4. Stop event (`detect_queue_events.py`, type `stop`)

A cyclist inside a crossing's start waiting area whose speed (from
`velocity_x`, `velocity_y`) stays below `STOP_SPEED` (0.5 m/s) for at least
`STOP_DURATION` (0.5 s). By default only each cyclist's first stop per area
counts (`EVERY_STOP`). A stop in an area where several crossings start is
recorded once per crossing. **Snapshot:** the first timestep of the stop.

### Snapshots

At each start or stop event's snapshot time, every cyclist is labelled:

- **inside**: in the start waiting area (same stay rule as occupancy);
- **near**: not inside, but within `NEAR_DISTANCE` (5 m) of the area's edge.

Their positions are stored in the crossing's local frame, in metres:
x is the distance behind the start line, y runs along it.

- `<P>_events.csv`: one row per start or stop event.
- `<P>_event_positions.csv`: the cyclists inside or near at each event.

## 5. Discharge (`detect_queue_events.py`, type `discharge`)

A stopped queue being released over the crossing's lines.

1. Each start event gets a **reference stop**: the latest stop event of the
   same crossing at or before it, at most `DISCHARGE_MAX_LAG` (120 s) earlier.
2. The **queue** is the cyclists inside the area with speed below
   `STOP_SPEED` at that stop's snapshot. `queue_position` 1 is the one
   nearest the start line.
3. There is one discharge per reference stop. Its trigger is one of:
   - `queue`: the first start event by a queue member. Earlier start events
     by other cyclists are counted as rolling starts (`n_skipped_starts`).
   - `rolling`: no queue member has a matched start event, so the first
     matched start event triggers it.
4. **Discharge passes**: for each queue member, its first forward pass of
   every line of the crossing (start, the N lines in between, end) after the
   stop's snapshot.

- `<P>_discharges.csv`: one row per discharge.
- `<P>_discharge_queues.csv`: each discharge's queue members.
- `<P>_discharge_passes.csv`: pass times per discharge, member and line.
- `view_discharges.py` shows them.

## Not implemented yet

Jam density (cyclists per m² of waiting area) and discharge rate (cyclists
per second over the start line) per event are still to do. They can be
computed from the queue and pass tables above. Measure areas in UTM
(`utm_x`, `utm_y`): in Web Mercator they come out about 2.2× too large.
