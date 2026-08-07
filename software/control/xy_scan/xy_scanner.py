import logging
import asyncio
import numpy as np

# Fixed hardware limits - cannot be exceeded physically
ROBOT_HARD_LIMITS = {
    "x_min": 0.0, "x_max": 1000.0,
    "y_min": -120.0, "y_max": 130.0,
    "z_min": -120.0, "z_max": 98.0
}


class XYScanRoutine:
    def __init__(self, dexarm, spectrometer, hdf5_manager):
        self.dexarm = dexarm
        self.spectrometer = spectrometer
        self.hdf5_manager = hdf5_manager

        # Default Settings
        self.x_min, self.x_max = 0.0, 50.0
        self.y_min, self.y_max = 0.0, 50.0
        self.z_plane = 0.0
        self.step_x = 5.0
        self.step_y = 5.0

        self.SAFETY_OVERRIDE_FLAG = False  # Set to True to bypass safety checks (use with caution)


    def _is_valid_hard_limit(self, x_min, x_max, y_min, y_max, z_plane):
        if not (ROBOT_HARD_LIMITS["z_min"] <= z_plane <= ROBOT_HARD_LIMITS["z_max"]):
            logging.error(
                f"Z Plane {z_plane:.1f}mm is OUT OF HARD LIMITS "
                f"[{ROBOT_HARD_LIMITS['z_min']:.1f}, {ROBOT_HARD_LIMITS['z_max']:.1f}]."
            )
            return False

        if not (
            ROBOT_HARD_LIMITS["x_min"] <= x_min <= ROBOT_HARD_LIMITS["x_max"] and
            ROBOT_HARD_LIMITS["x_min"] <= x_max <= ROBOT_HARD_LIMITS["x_max"]
        ):
            logging.error(
                f"X Bounds [{x_min:.1f}, {x_max:.1f}] are OUT OF HARD LIMITS "
                f"[{ROBOT_HARD_LIMITS['x_min']:.1f}, {ROBOT_HARD_LIMITS['x_max']:.1f}]."
            )
            return False

        if not (
            ROBOT_HARD_LIMITS["y_min"] <= y_min <= ROBOT_HARD_LIMITS["y_max"] and
            ROBOT_HARD_LIMITS["y_min"] <= y_max <= ROBOT_HARD_LIMITS["y_max"]
        ):
            logging.error(
                f"Y Bounds [{y_min:.1f}, {y_max:.1f}] are OUT OF HARD LIMITS "
                f"[{ROBOT_HARD_LIMITS['y_min']:.1f}, {ROBOT_HARD_LIMITS['y_max']:.1f}]."
            )
            return False

        return True


    async def configure(self):
        loop = asyncio.get_running_loop()

        z_plane_temp = self.z_plane
        x_min_temp, x_max_temp = self.x_min, self.x_max
        y_min_temp, y_max_temp = self.y_min, self.y_max
        step_x_temp = self.step_x
        step_y_temp = self.step_y

        try:
            curr_x, curr_y, curr_z = await self.dexarm.get_translated_position()
            disp_z = curr_z - 300

            print(f"\n--- XY Scan Configuration ---")
            use_curr = await loop.run_in_executor(
                None,
                lambda: input(
                    f"Use current Z ({disp_z:.1f} mm) as scan plane? (y/n): "
                ).strip().lower()
            )

            if use_curr == 'y':
                z_plane_temp = disp_z
            else:
                raw = await loop.run_in_executor(
                    None, lambda: input("Enter Z Plane (mm): ").strip()
                )
                if raw:
                    z_plane_temp = float(raw)

            raw = await loop.run_in_executor(
                None,
                lambda: input(
                    f"X-Axis [Min, Max] (current {self.x_min}, {self.x_max}): "
                ).strip()
            )
            if raw:
                x_min_temp, x_max_temp = map(float, raw.split(","))

            raw = await loop.run_in_executor(
                None, lambda: input(f"X Step (current {self.step_x}): ").strip()
            )
            if raw:
                step_x_temp = float(raw)

            raw = await loop.run_in_executor(
                None,
                lambda: input(
                    f"Y-Axis [Min, Max] (current {self.y_min}, {self.y_max}): "
                ).strip()
            )
            if raw:
                y_min_temp, y_max_temp = map(float, raw.split(","))

            raw = await loop.run_in_executor(
                None, lambda: input(f"Y Step (current {self.step_y}): ").strip()
            )
            if raw:
                step_y_temp = float(raw)

        except (ValueError, IndexError):
            logging.error("Invalid numeric input. Configuration failed.")
            return False

        if not self._is_valid_hard_limit(
            x_min_temp, x_max_temp, y_min_temp, y_max_temp, z_plane_temp
        ):
            logging.warning("Configuration aborted due to out-of-hard-limits input.")
            return False

        self.z_plane = z_plane_temp
        self.x_min, self.x_max = x_min_temp, x_max_temp
        self.y_min, self.y_max = y_min_temp, y_max_temp
        self.step_x = step_x_temp
        self.step_y = step_y_temp

        logging.info(
            f"Config: X[{self.x_min:.1f}:{self.x_max:.1f}:{self.step_x:.1f}], "
            f"Y[{self.y_min:.1f}:{self.y_max:.1f}:{self.step_y:.1f}], "
            f"Z={self.z_plane:.1f}"
        )
        return True


    async def run(self):
        if not self.spectrometer:
            logging.error("Spectrometer not available.")
            return

        x_points = np.arange(self.x_min, self.x_max + 0.001, self.step_x)
        y_points = np.arange(self.y_min, self.y_max + 0.001, self.step_y)

        if len(x_points) == 0 or len(y_points) == 0:
            logging.error("Scan range is empty. Check min/max/step configuration.")
            await self.dexarm.sequential_home_zyx()
            return

        total = len(x_points) * len(y_points)
        logging.info(
            f"Starting Scan: {len(x_points)} cols x {len(y_points)} rows "
            f"({total} points)"
        )

        spectra, x_map, y_map, int_times = [], [], [], []
        current_int = self.spectrometer.integration_time_us

        await self.dexarm.safe_move_to(z=-100, safety_override=self.SAFETY_OVERRIDE_FLAG)

        await self.dexarm.sequential_move_xyz(
            x=x_points[0], y=y_points[0], z=self.z_plane,
            safety_override=self.SAFETY_OVERRIDE_FLAG
        )

        count = 0

        for i, y in enumerate(y_points):
            progress = (i / len(y_points)) * 100.0
            #y_label = "y_min" if i == 0 else "y_min+y_step"

            print(
                f"\nMeasuring at y = {y:.1f} | Progress {progress:.0f}%"
            )

            await self.dexarm.safe_move_to(
                y=y, partial=True, safety_override=self.SAFETY_OVERRIDE_FLAG
            )
            await self.dexarm.safe_move_to(
                x=x_points[0], partial=True, safety_override=self.SAFETY_OVERRIDE_FLAG
            )

            if i > 0:
                await asyncio.sleep(10)

            for j, x in enumerate(x_points):
                await self.dexarm.safe_move_to(
                    x=x, partial=True, safety_override=self.SAFETY_OVERRIDE_FLAG
                )

                await asyncio.sleep(2)

                spec = await self.spectrometer.read_spectrum()
                peak = float(np.max(spec))

                spectra.append(spec)
                x_map.append(x)
                y_map.append(y)
                int_times.append(current_int)

                count += 1

                logging.info(
                    f"Row {i + 1}: Col{j + 1}: "
                    f"X={x:.1f}, y={y:.1f}, Z={self.z_plane:.1f} | "
                    f"Data captured | Signal Peak: {peak:.0f}"
                )

        print("\nScan Complete.")
        await self.dexarm.sequential_home_zyx()

        n_rows = len(y_points)
        n_cols = len(x_points)
        n_wav = len(self.spectrometer.wavelengths)

        data = {
            "spectra": np.array(spectra, dtype=np.float32).reshape(
                n_rows, n_cols, n_wav
            ),
            "x_map": np.array(x_map, dtype=np.float32).reshape(n_rows, n_cols),
            "y_map": np.array(y_map, dtype=np.float32).reshape(n_rows, n_cols),
            "integration_times": np.array(
                int_times, dtype=np.int32
            ).reshape(n_rows, n_cols),
            "wavelengths": self.spectrometer.wavelengths,
            "settings": {
                "x_min": self.x_min,
                "x_max": self.x_max,
                "step_x": self.step_x,
                "y_min": self.y_min,
                "y_max": self.y_max,
                "step_y": self.step_y,
                "z_plane": self.z_plane
            }
        }

        self.hdf5_manager.save_scan_data(data)
