import json
import csv
import pandas as pd
import glob

from numpy.f2py.symbolic import as_real

json.loads('{"categories": {"car": 1, "pedestrian": 2, "bicycle": 3, "trailer": 4, "motorcycle": 5, "truck": 6, "bus": 7, "scooter": 8, "streetcar": 9}, "coordinates": {"global": "UTM32N", "offset_x": 692009.0, "offset_y": 5338095.0}, "reference_time": {"0": "14:59:25"}}')


# Get all CSV files in a folder
csv_files = glob.glob("TUMDOT - MUC - Download/Trajectory Data/*.csv")
# Read and combine
df = pd.concat(
    (pd.read_csv(file) for file in csv_files),
    ignore_index=True)
# Save to a new CSV
df.to_csv("TUMDOT - MUC - Download/Trajectory Data/combined_TUMDOT.csv", index=False)

#Visualization


#Queue discharge rate calculation
time_steps_queues = []
queue_locations 
for time_step in time_steps_queues:
    for location in queue_locations do:
        a= calculate queue dimensions
        b= calculate number of bikes in the area
        jam density = b/a

        c=get time of last cyclist exiting the waiting area
        d=get time of first cyclist exiting the waiting area
        discharge time = c-d
        N = number of cyclists passing the exit line of the waiting area in the discharge time
        discharge rate = N/discharge time
