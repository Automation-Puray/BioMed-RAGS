# /home/Biomed/fiber_gonio/Refactor/devices/robot_limits.py
import json
import logging
#  Configuration Path 
CALIBRATION_JSON_PATH = "/home/Biomed/fiber_gonio/Refactor/calibration.json"

#  Fixed hardware limits - cannot be exceeded physically
ROBOT_HARD_LIMITS = {
    "x_min": 0.0, "x_max": 1000.0,
    "y_min": -100.0, "y_max": 130.0,
    "z_min": -120.0, "z_max": 60.0
}

class RobotBoundaryManager:
    def __init__(self, config_path=CALIBRATION_JSON_PATH):
        self.config_path = config_path
        self.reload_config()
        with open(config_path, 'r') as f:
            config = json.load(f)

        self.experiment_profiles = config.get("experiment_profiles", {})
        
        self.safe_park_coordinates = {
            'x': config["safe_Park_X"],
            'y': config["safe_Park_Y"],
            'z': config["safe_Park_Z"]
        }
        if not all(k in config for k in ["safe_Park_X", "safe_Park_Y", "safe_Park_Z"]):
            raise ValueError("Missing safe_Park_X, safe_Park_Y, or safe_Park_Z in calibration.json.")
       
        self.current_experiment_name = None
    
    def reload_config(self):
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        self.experiment_profiles = config.get("experiment_profiles", {})
        self.safe_park_coordinates = {
            'x': config["safe_Park_X"],
            'y': config["safe_Park_Y"],
            'z': config["safe_Park_Z"]
        }
    def set_experiment(self, name: str):
        if name in self.experiment_profiles:
            self.current_experiment_name = name
            logging.info(f"Experiment bounds loaded: {name}")
        else:
            self.current_experiment_name = None
            logging.info(f"No experiment profile found for '{name}'. Using system bounds.")
    def is_within_hard_limits(self, x, y, z):
        return (
            ROBOT_HARD_LIMITS["x_min"] <= x <= ROBOT_HARD_LIMITS["x_max"] and
            ROBOT_HARD_LIMITS["y_min"] <= y <= ROBOT_HARD_LIMITS["y_max"] and
            ROBOT_HARD_LIMITS["z_min"] <= z <= ROBOT_HARD_LIMITS["z_max"]
        )

    def is_within_experiment_bounds(self, x, y, z):
        if not self.current_experiment_name:
            return True  # No experiment loaded, allow move
        bounds = self.experiment_profiles.get(self.current_experiment_name)
        if not bounds or not all(k in bounds for k in ['x_min', 'x_max', 'y_min', 'y_max', 'z_min', 'z_max']):
            logging.info(f"Warning: Active experiment '{self.current_experiment_name}' profile is missing or malformed.")
            return True
        return (
            bounds["x_min"] - 1 <= x <= bounds["x_max"] + 1 and
            bounds["y_min"] - 1 <= y <= bounds["y_max"] + 1 and
            bounds["z_min"] - 2 <= z <= bounds["z_max"] + 2
        )

    def is_position_safe(self, x, y, z):
        #z = z - 300.0
        is_safe = self.is_within_hard_limits(x, y, z) and self.is_within_experiment_bounds(x, y, z)
        if not is_safe:
            logging.warning(f"Unsafe position detected: (x={x}, y={y}, z={z})")
            logging.warning(f"Hard Limits OK: {self.is_within_hard_limits(x, y, z)}")
            logging.warning(f"Experiment Bounds OK: {self.is_within_experiment_bounds(x, y, z)}")
        return is_safe
    def get_safe_park_coordinates(self):
        return self.safe_park_coordinates
