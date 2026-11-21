# COCO class ids that are traffic relevant -> our category names.
VEHICLE_CLASSES: dict[int, str] = {1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
CLASS_IDS_BY_NAME = {v: k for k, v in VEHICLE_CLASSES.items()}
ALL_CATEGORIES = list(VEHICLE_CLASSES.values())

# BGR colours used in annotated frames
CLASS_COLORS = {
    "car": (255, 160, 40),
    "motorcycle": (60, 200, 255),
    "bus": (80, 220, 120),
    "truck": (60, 120, 255),
    "bicycle": (220, 120, 255),
}

DENSITY_LEVELS = ["Low", "Moderate", "High", "Critical"]
DEFAULT_DENSITY_THRESHOLDS = (0.25, 0.5, 0.75)  # occupancy ratio boundaries
