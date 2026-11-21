# Computer-vision pipeline

`Video input -> frame extraction -> YOLO11 detection -> ByteTrack -> classification -> counting lines -> density -> violation analysis -> DB -> WebSocket -> dashboard`

Code: `backend/app/cv/` (`detector.py`, `pipeline.py`, `counting.py`, `density.py`, `violations.py`, `annotate.py`, `evidence.py`, `video_io.py`).

## Counting
The anchor point is the box centre. A track is counted on a line when the segment between its previous and current centre crosses the **line segment**. Direction `in` means moving from the negative to the positive side of `p1 -> p2` (for a left-to-right horizontal line that is top-to-bottom). A track is counted at most once per line.

## Density
`occupancy = vehicles inside density zone / zone capacity` (capacity = vehicles that mean "full", editable). Default thresholds 25 / 50 / 75 % -> Low / Moderate / High / Critical. With no density zone the whole frame is used with capacity 15.

## Violation modules (all off until configured)
| Module | Needs | Rule |
|---|---|---|
| Wrong-way | "Wrong-way lane" zone with allowed direction | inside zone, moved >1.5 % of the frame diagonal over >=0.6 s, direction opposite (cos < -0.5) for 6 consecutive checks |
| Restricted zone | "Restricted" zone | centre inside for >= dwell seconds (default 1 s) |
| Overspeed | speed calibration (metres per pixel) | smoothed speed above limit for >= 1 s |
| Red light | enabled signal + stop line | crosses the stop line in the chosen direction while the **configured** state is red |

Each violation is emitted once per vehicle and module, stores timestamp, track id, category, severity, details, and an annotated screenshot.

## Speed estimation limits
Estimating speed from a single camera is approximate: (1) one metres-per-pixel value assumes a flat road, but perspective makes the true scale change along the image - far vehicles look slower; (2) boxes jitter, so speed is smoothed; (3) camera shake, lens distortion and vehicles moving across the line of sight add error; (4) frame-rate and stride matter. Calibrate with a known length (lane marking, car length) **near the lane of interest** (Settings -> Cameras and zones -> Speed scale). Use results as indicative, not as legal evidence. A homography calibration (4 known ground points) would be the next improvement.

## Red-light limitation
The system does not read the colour of a traffic light in the frame. The signal state is configured (manual or a fixed cycle matching the real signal). It is only as correct as that configuration.

## Performance tips
Speed depends heavily on your hardware (it was not benchmarked in the build environment). Use `yolo11n.pt`, frame skipping ("Every 2nd/3rd frame"), a smaller inference size in Settings, or a GPU.
