import h5py
import os
import numpy as np
import logging
from datetime import datetime


CALIBRATION_PATH = "/home/Biomed/fiber_gonio/Refactor/devices/xy_scan/calibration.npy"


class XYHDF5Manager:
    def __init__(self, experiment_name: str):
        self.experiment_name = experiment_name
        self.file = None
        self.file_path = None

        base_dir = os.path.join(os.path.dirname(__file__), "XY_HDF5_Files")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        self.base_dir = base_dir

    def create_file(self):
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

        filename = f"{self.experiment_name}_{timestamp}.h5"
        self.file_path = os.path.join(self.base_dir, filename)

        try:
            self.file = h5py.File(self.file_path, 'w')

            self.file.attrs['experiment_name'] = self.experiment_name
            self.file.attrs['creation_date'] = now.strftime("%Y-%m-%d")
            self.file.attrs['creation_timestamp'] = timestamp

            # Ensure measurement group exists
            self.file.require_group("XY_Grid_Measurement")

            self.file.flush()
            logging.info(f"HDF5 file created at: {self.file_path}")

            # Load and store calibration immediately for this experiment
            self.save_calibration()

            return self.file_path
        except Exception as e:
            logging.error(f"Error creating HDF5 file: {e}")
            self.file = None
            return None

    def write_spectrometer_metadata(self, integration_time_us: int, sensor_area_cm2: float):
        if not self.file:
            return
        try:
            meta_group = self.file.require_group("Spectrometer_Metadata")
            meta_group.attrs['integration_time_us'] = integration_time_us
            meta_group.attrs['sensor_area_cm2'] = sensor_area_cm2
            self.file.flush()
        except Exception as e:
            logging.error(f"Error writing metadata: {e}")

    def save_calibration(self):
        """
        Load calibration.npy and store as dataset 'Calibration'
        under /XY_Grid_Measurement.
        """
        if not self.file:
            logging.warning("HDF5 file not open.")
            return

        try:
            if not os.path.exists(CALIBRATION_PATH):
                logging.error(f"Calibration file not found: {CALIBRATION_PATH}")
                return

            calibration = np.load(CALIBRATION_PATH)

            grp = self.file.require_group("XY_Grid_Measurement")

            # Overwrite if already present
            if "Calibration" in grp:
                del grp["Calibration"]

            grp.create_dataset("Calibration", data=calibration)

            self.file.flush()
            logging.info("Calibration data saved to HDF5.")
        except Exception as e:
            logging.error(f"Failed to save calibration data: {e}")

    def save_dark_spectrum(self, spectrum: np.ndarray):
        if not self.file:
            logging.warning("HDF5 file not open.")
            return

        try:
            grp = self.file.require_group("XY_Grid_Measurement")

            if "Dark_Spectrum" in grp:
                del grp["Dark_Spectrum"]

            grp.create_dataset(
                "Dark_Spectrum",
                data=np.asarray(spectrum, dtype=np.float32)
            )

            self.file.flush()
            logging.info("Dark Spectrum Captured and Saved.")
        except Exception as e:
            logging.error(f"Failed to save dark spectrum: {e}")

    def save_scan_data(self, data: dict):
        if not self.file:
            logging.warning("HDF5 file not open.")
            return

        try:
            grp = self.file.require_group("XY_Grid_Measurement")

            for name in ["Spectra", "Integration_Times", "Wavelengths", "x_map", "y_map"]:
                if name in grp:
                    del grp[name]

            grp.create_dataset("Spectra", data=data['spectra'], compression="gzip")
            grp.create_dataset("x_map", data=data['x_map'], compression="gzip")
            grp.create_dataset("y_map", data=data['y_map'], compression="gzip")
            grp.create_dataset("Wavelengths", data=data['wavelengths'])

            if 'integration_times' in data:
                grp.create_dataset("Integration_Times", data=data['integration_times'])

            settings = data.get('settings', {})
            for k, v in settings.items():
                grp.attrs[k] = v

            self.file.flush()
            logging.info("Scan data saved successfully.")
        except Exception as e:
            logging.error(f"Failed to save scan data: {e}")

    def close(self):
        if self.file:
            self.file.close()
            logging.info("HDF5 file closed.")
            self.file = None
