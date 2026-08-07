import h5py
import os
import numpy as np
import logging
from datetime import datetime

class HDF5Manager:
    def __init__(
        self,
        fiber_id,
        fiber_code,
        exp_id,
        exp_code,
        cath_id=None,
        cath_code=None,
        category="single",
        base_dir="/home/Biomed/fiber_gonio/Refactor/HDF5_Files"
    ):
        self.base_dir = base_dir
        self.file_path = None
        self.fiber_id = fiber_id
        self.exp_id = exp_id
        self.cath_id = cath_id
        self.fiber_code = fiber_code
        self.exp_code = exp_code
        self.cath_code = cath_code
        self.category = category
        self.file = None
        self._global_maps_written = False

    def create_file(self):
        fiber_dir = os.path.join(self.base_dir, self.fiber_code)
        os.makedirs(fiber_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{self.exp_code}_{timestamp}.h5"
        self.file_path = os.path.join(fiber_dir, filename)

        try:
            self.file = h5py.File(self.file_path, "w")

            self.file.attrs["fiber_id"] = self.fiber_id
            self.file.attrs["exp_id"] = self.exp_id
            self.file.attrs["fiber_code"] = str(self.fiber_code)
            self.file.attrs["exp_code"] = str(self.exp_code)
            self.file.attrs["category"] = str(self.category)

            if self.cath_id:
                self.file.attrs["cath_id"] = self.cath_id
            if self.cath_code:
                self.file.attrs["cath_code"] = str(self.cath_code)

            self.file.attrs["creation_date"] = datetime.now().strftime("%Y-%m-%d")
            self.file.attrs["creation_timestamp"] = datetime.now().isoformat()

            self.file.create_group("Experiment_Setup")
            self.file.create_group("Experiment_Bounds")
            self.file.create_group("Measurements")
            self.file.create_group("PM400")

            self.file.flush()
            logging.info(f"HDF5 File created: {self.file_path}")
            return True

        except Exception as e:
            logging.error(f"Failed to create HDF5 file: {e}")
            return False

    def write_experiment_bounds(
        self,
        bounds,
        setup,
        global_maps,
        laser_source,
        lte_duration_min=None,
        lte_interval_min=None,
    ):
        if not self.file or self._global_maps_written:
            return

        try:
            grp = self.file["Experiment_Bounds"]

            grp.create_dataset(
                "robot_bounds",
                data=np.array(
                    [
                        bounds.get("x_min"),
                        bounds.get("x_max"),
                        bounds.get("y_max"),
                        bounds.get("z_max"),
                    ],
                    dtype=np.float64,
                ),
            )

            grp.attrs["measurement_step_distance"] = setup.get("measurement_step_distance")
            grp.attrs["rotation_step"] = setup.get("rotation_step")

            # ✅ LTE ATTRIBUTES (ONLY FOR long_term)
            if self.category == "long_term":
                grp.attrs["total_duration_minutes"] = float(lte_duration_min or 0)
                grp.attrs["measurement_interval_minutes"] = float(lte_interval_min or 0)

            dt = h5py.string_dtype(encoding="utf-8")
            grp.create_dataset("laser_source", data=str(laser_source), dtype=dt)

            for name in ("deg_map", "x_raw_map", "x_ref_map"):
                grp.create_dataset(
                    name,
                    data=np.asarray(global_maps[name]),
                    compression="gzip",
                )

            self._global_maps_written = True
            self.file.flush()

        except Exception as e:
            logging.error(f"Failed to write Experiment_Bounds: {e}")

    def write_pm400_data(self, history, final_setpoint, final_measured_power):
        if not self.file:
            return

        try:
            grp = self.file["PM400"]

            if final_setpoint is not None:
                grp.attrs["final_setpoint"] = final_setpoint
            if final_measured_power is not None:
                grp.attrs["final_measured_power"] = final_measured_power

            if history is not None:
                history_np = np.array(history)
                if "history" in grp:
                    del grp["history"]
                grp.create_dataset("history", data=history_np)

                if history_np.ndim == 2 and history_np.shape[1] >= 2:
                    grp.create_dataset("setpoints", data=history_np[:, 0])
                    grp.create_dataset("measured_powers", data=history_np[:, 1])

            self.file.flush()

        except Exception as e:
            logging.error(f"Failed to write PM400 data: {e}")

    def save_cycle_data(self, cycle_index, cycle_data):
        if not self.file:
            logging.warning("HDF5 file not open.")
            return

        try:
            meas_grp = self.file["Measurements"]
            cycle_name = f"Cycle_{cycle_index}"

            if cycle_name in meas_grp:
                del meas_grp[cycle_name]

            c_grp = meas_grp.create_group(cycle_name)

            if "times" in cycle_data:
                t_grp = c_grp.create_group("Measurement_Times")
                t_grp.create_dataset(
                    "times",
                    data=np.array(
                        [
                            cycle_data["times"].get("start", ""),
                            cycle_data["times"].get("end", ""),
                        ],
                        dtype=h5py.string_dtype("utf-8"),
                    ),
                )

            if "airq" in cycle_data:
                e_grp = c_grp.create_group("Environment_Data")
                aq = cycle_data["airq"]

                e_grp.create_dataset(
                    "temperature",
                    data=np.array(
                        [aq.get("temp_start", 0), aq.get("temp_end", 0)],
                        dtype=np.float64,
                    ),
                )

                e_grp.create_dataset(
                    "humidity",
                    data=np.array(
                        [aq.get("humid_start", 0), aq.get("humid_end", 0)],
                        dtype=np.float64,
                    ),
                )

            if "spectrometer" in cycle_data:
                spec = cycle_data["spectrometer"]

                s_grp = c_grp.create_group("Spectrometer")
                s_grp.attrs["sensor_area_cm2"] = spec["sensor_area_cm2"]

                for key in (
                    "wavelengths",
                    "spectra",
                    "dark_spectrum",
                    "calibration_factors",
                    "integration_times",
                ):
                    data = np.asarray(spec[key])

                    chunks = None
                    if data.ndim == 3:
                        chunks = (1, 1, data.shape[2])
                    elif data.ndim == 2:
                        chunks = (1, data.shape[1])

                    s_grp.create_dataset(
                        key,
                        data=data,
                        compression="gzip",
                        chunks=chunks,
                    )

            self.file.flush()
            logging.info(f"Saved {cycle_name} to HDF5.")

        except Exception as e:
            logging.error(f"Failed to save {cycle_name}: {e}")

    def save_global_setup(self, data: dict):
        if "pm400" in data:
            pm = data["pm400"]
            self.write_pm400_data(
                pm.get("history"),
                pm.get("final_setpoint"),
                pm.get("final_measured_power"),
            )

    def close(self):
        if self.file:
            self.file.close()
            logging.info("HDF5 file closed.")
            self.file = None
