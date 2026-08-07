# /home/Biomed/fiber_gonio/Refactor/devices/measurement_routine.py
import json
import logging
import asyncio
import math
import numpy as np
from Refactor.devices.dexarm_controller import DexArmController
from Refactor.devices.arduino_stage import ArduinoStage
from Refactor.devices.spectrometer import AsyncFlame, T_INTEGRATION_MIN 
from Refactor.devices.laser_control import LaserController
from Refactor.devices.pm400 import PM400
from Refactor.devices.spectro_optimizer import SpectrometerOptimizer

ROTATION_START = 0
ROTATION_END = 360


class MeasurementLoop:
    def __init__(self, dexarm: DexArmController, arduino_stage: ArduinoStage, spectrometer: AsyncFlame,
                 laser_control: LaserController, pm400: PM400, experiment_data=None, laser_source=""):
        self.dexarm = dexarm
        self.arduino_stage = arduino_stage
        self.spectrometer = spectrometer
        self.laser_control = laser_control
        self.laser_source = laser_source
        self.pm400 = pm400
        self.initial_laser_setpoint = 0
        self.measurement_step_distance = 10
        self.rotation_step = 30

        # Data Containers
        self.spectrometer_data = []
        self.dark_dictionary = {}  
        self.deg_map_list = []
        self.x_raw_map_list = []
        self.x_ref_map_list = []
        self.recorded_integration_times = []
        # Reference to the shared dictionary
        self.experiment_data = experiment_data if experiment_data is not None else {}

        self.optimizer = SpectrometerOptimizer(self.spectrometer, self.dexarm, self.laser_control)
        
    async def reset_bounds(self):
        experiment = self.dexarm.boundary_manager.current_experiment_name
        if not experiment:
            logging.warning("No active experiment selected.")
            return

        x, y, z = await self.dexarm.get_translated_position()
        z_offset = z - 300
        config_path = self.dexarm.boundary_manager.config_path

        try:
            with open(config_path, 'r+') as f:
                data = json.load(f)

                if experiment not in data.get("experiment_profiles", {}):
                    logging.warning(f"Experiment '{experiment}' not found in config.")
                    return

                bounds = data["experiment_profiles"][experiment]
                bounds["x_max"] = round(x, 2)
                bounds["y_max"] = round(y, 2)
                bounds["z_max"] = round(z_offset, 2)

                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()

                logging.info("Boundary values updated.")
                self.dexarm.boundary_manager.reload_config()

        except Exception:
            logging.exception("Failed to update experiment bounds.")

    async def take_single_spectrum(self):
        if self.spectrometer is None:
            logging.error("Spectrometer not initialized.")
            return
        try:
            if self.laser_control:
                await self.laser_control.set_power(self.initial_laser_setpoint)
            raw_spectrum_signal = await self.spectrometer.read_spectrum()

            if self.laser_control:
                await self.laser_control.set_power(0)
            await asyncio.sleep(0.5)
            raw_spectrum_dark = await self.spectrometer.read_spectrum()

            if self.laser_control:
                await self.laser_control.set_power(self.initial_laser_setpoint)

            is_saturated, peak, pct = self.spectrometer.check_saturation(raw_spectrum_signal)
            logging.info(f"Peak: {peak:.0f} (Saturation: {pct:.1f}%)")

        except Exception as e:
            logging.error(f"Error taking spectrum: {e}")

    async def rotate_stage_manual(self):
        loop = asyncio.get_running_loop()
        try:
            angle_str = await loop.run_in_executor(None, lambda: input("Enter rotation angle (degrees): ").strip())
            angle = float(angle_str)
            await self.arduino_stage.send_angle(angle)
            await asyncio.sleep(2)
            logging.info(f"Stage rotated to {angle}°.")
        except Exception as e:
            logging.error(f"Error rotating stage: {e}")

    async def _capture_dark_dictionary(self):
        unique_times = sorted(set(self.recorded_integration_times))
        for t_us in unique_times:
            await self.spectrometer.set_integration_time(t_us)
            await asyncio.sleep(0.3)
            self.dark_dictionary[t_us] = await self.spectrometer.read_spectrum()

    async def start_goniometric_measurement(self):
        """Run the measurement and always attempt to switch the laser off."""
        try:
            await self._run_goniometric_measurement()
        finally:
            if self.laser_control:
                try:
                    await self.laser_control.set_power(0)
                    logging.info("Fail-safe laser shutdown completed.")
                except Exception:
                    logging.exception(
                        "Fail-safe laser shutdown command failed."
                    )


    async def _run_goniometric_measurement(self):
        profile = self.dexarm.boundary_manager.experiment_profiles.get(
            self.dexarm.boundary_manager.current_experiment_name
        )
        if not profile:
            raise RuntimeError("No active experiment profile")

        x_min, x_max = profile["x_min"], profile["x_max"]
        y_max, z_max = profile["y_max"], profile["z_max"]

        steps = []
        x = x_max
        while x >= x_min:
            steps.append(x)
            x -= self.measurement_step_distance

        angles = list(range(ROTATION_START, ROTATION_END, int(self.rotation_step)))

        self.spectrometer_data.clear()
        self.deg_map_list.clear()
        self.x_raw_map_list.clear()
        self.x_ref_map_list.clear()
        self.recorded_integration_times.clear()

        current_it = T_INTEGRATION_MIN

        # First go to experiment start
        entry_ok = await self.dexarm.move_to_experiment_entry(x=x_max, y=y_max, z=z_max)
        if not entry_ok:
            raise RuntimeError("Failed to reach experiment start position safely.")

        await asyncio.sleep(3)  # settle at x_max, y_max, z_max

        # Then warm up laser there
        if self.laser_control:
            await self.laser_control.set_power(self.initial_laser_setpoint)
            await asyncio.sleep(2)
            logging.info("Waiting 120 s for laser to stabilize before first measurement...")
            await asyncio.sleep(1) # change it back to 120

        for i, angle in enumerate(angles):
            if i > 0:
                await self.arduino_stage.send_angle(self.rotation_step)
                await asyncio.sleep(1)
                await self.dexarm.sequential_move_xyz(x=x_max, y=y_max, z=z_max)
                await asyncio.sleep(15)

            logging.info(f"MEASURING AT ANGLE: {angle}°")

            for x_pos in steps:
                result = await self.optimizer.run_live_measurement_point(
                    x_pos=x_pos,
                    y_pos=y_max,
                    z_pos=z_max,
                    seed_time_us=current_it,
                )
                current_it = result["integration_time"]

                self.spectrometer_data.append(result["spectrum"])
                self.recorded_integration_times.append(current_it)
                self.deg_map_list.append(angle)
                self.x_raw_map_list.append(x_pos)
                self.x_ref_map_list.append(x_max - x_pos)

        if self.laser_control:
            await self.laser_control.set_power(0)
            await asyncio.sleep(2)

        await self._capture_dark_dictionary()
        self.prepare_data_for_hdf5(angles, steps)

    def prepare_data_for_hdf5(self, angles, steps):
        num_angles = len(angles)
        num_steps = len(steps)

        wavelengths = np.asarray(self.spectrometer.wavelengths, dtype=np.float32)

        spectra = np.asarray(self.spectrometer_data, dtype=np.float32)
        dark = np.asarray(
            [self.dark_dictionary[t] for t in self.recorded_integration_times],
            dtype=np.float32,
        )

        self.experiment_data["spectrometer"] = {
            "wavelengths": wavelengths,
            "spectra": spectra.reshape(num_angles, num_steps, -1),
            "dark_spectrum": dark.reshape(num_angles, num_steps, -1),
            "integration_times": np.asarray(self.recorded_integration_times).reshape(
                num_angles, num_steps
            ),
            "calibration_factors": np.asarray(self.spectrometer._calibration),
            "sensor_area_cm2": self.spectrometer.sensor_area_cm2,
        }

        self.experiment_data["global_maps"] = {
            "deg_map": np.asarray(self.deg_map_list).reshape(num_angles, num_steps),
            "x_raw_map": np.asarray(self.x_raw_map_list).reshape(num_angles, num_steps),
            "x_ref_map": np.asarray(self.x_ref_map_list).reshape(num_angles, num_steps),
        }

        self.experiment_data["experiment_setup"] = {
            "measurement_step_distance": self.measurement_step_distance,
            "rotation_step": self.rotation_step,
        }

        logging.info("Spectrometer data prepared successfully for HDF5.")