# /home/Biomed/fiber_gonio/Refactor/devices/manual_control.py

import asyncio
import sys
import logging
import time
from datetime import datetime
from Refactor.devices.dexarm_controller import DexArmController
from Refactor.devices.measurement_routine import MeasurementLoop
from Refactor.devices.server_api_client import ServerAPIClient
from Refactor.devices.airq import AirQClient

MOVE_STEPS = [200, 100, 50, 20, 10, 5, 1]


def _get_key_sync():
    try:
        import msvcrt
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch in (b"\x00", b"\xe0"):
                ch = msvcrt.getch()
                return {b"H": "UP", b"P": "DOWN", b"K": "LEFT", b"M": "RIGHT"}.get(ch, "")
            return "ENTER" if ch == b"\r" else ch.decode()
        return None
    except ImportError:
        import tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            c = sys.stdin.read(1)
            if c == "\x03":
                raise KeyboardInterrupt
            if c == "\x1b":
                seq = sys.stdin.read(2)
                return {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT"}.get(seq, "")
            return "ENTER" if c in ("\r", "\n") else c
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


async def get_key():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _get_key_sync)


def _get_manual_coord_sync():
    try:
        logging.info("Enter manual coordinates (leave blank to skip an axis):")
        x = input("X: ")
        y = input("Y: ")
        z = input("Z: ")
        x = float(x) if x.strip() else None
        y = float(y) if y.strip() else None
        z = float(z) if z.strip() else None
        return x, y, z
    except ValueError:
        logging.info("Invalid input.")
        return _get_manual_coord_sync()


async def get_manual_coord():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _get_manual_coord_sync)


class ManualDexArmController:
    def __init__(
        self,
        dexarm: DexArmController,
        mode="system",
        laser_control=None,
        pm400=None,
        spectrometer=None,
        arduino_stage=None,
        experiment_data=None,
        hdf5_manager=None,
        initial_laser_setpoint=None,
        laser_source="",
        category="single",
        lte_params=None # New: Pass {duration, interval, num_cycles} here
    ):
        self.dexarm = dexarm
        self.x, self.y, self.z_offset = None, None, None
        self.step_index = MOVE_STEPS.index(20)
        self.mode = mode
        self.measurement_routine = MeasurementLoop(
            self.dexarm,
            arduino_stage,
            spectrometer,
            laser_control,
            pm400,
            experiment_data=experiment_data,
            laser_source=laser_source,
        )
        self.laser_control = laser_control
        self.pm400 = pm400
        self.limits_enabled = True
        self.hdf5_manager = hdf5_manager
        self.experiment_data = experiment_data if experiment_data is not None else {}
        self.spectrometer = spectrometer
        self.initial_laser_setpoint = initial_laser_setpoint
        self.category = category
        self.airq = AirQClient()

        # LTE parameters passed from main.py
        if lte_params:
            self.lte_duration_min = lte_params.get('duration', 0)
            self.lte_interval_min = lte_params.get('interval', 0)
            self.lte_num_cycles = lte_params.get('num_cycles', 0)
        else:
            self.lte_duration_min = 0
            self.lte_interval_min = 0
            self.lte_num_cycles = 0

    def is_safe(self, x, y, z_offset):
        if not self.limits_enabled:
            return True
        if self.mode == "experiment":
            return self.dexarm.boundary_manager.is_position_safe(x, y, z_offset)
        else:
            return self.dexarm.boundary_manager.is_within_hard_limits(x, y, z_offset)

    async def move_by(self, dx=0, dy=0, dz=0):
        if self.x is None or self.y is None or self.z_offset is None:
            current_x, current_y, current_z = await self.dexarm.get_translated_position()
            self.x, self.y, self.z_offset = current_x, current_y, current_z - 300

        step = MOVE_STEPS[self.step_index]
        new_x = self.x + dx * step
        new_y = self.y + dy * step
        new_z_offset = self.z_offset + dz * step

        if self.is_safe(new_x, new_y, new_z_offset):
            await self.dexarm.move_to(new_x, new_y, new_z_offset)
            self.x, self.y, self.z_offset = new_x, new_y, new_z_offset
        else:
            logging.info(f"Out of bounds. Rejected: X={new_x:.1f}, Y={new_y:.1f}, Z={new_z_offset:.2f}")

    async def manual_coord_move(self):
        x_input, y_input, z_input_offset = await get_manual_coord()
        if self.x is None or self.y is None or self.z_offset is None:
            current_x, current_y, current_z = await self.dexarm.get_translated_position()
            self.x, self.y, self.z_offset = current_x, current_y, current_z - 300
        new_x = x_input if x_input is not None else self.x
        new_y = y_input if y_input is not None else self.y
        new_z_offset = z_input_offset if z_input_offset is not None else self.z_offset
        if self.is_safe(new_x, new_y, new_z_offset):
            await self.dexarm.sequential_move_xyz(
                x=new_x, y=new_y, z=new_z_offset, safety_override=not self.limits_enabled,
            )
            self.x, self.y, self.z_offset = new_x, new_y, new_z_offset
        else:
            logging.info(f"Out of bounds. Rejected: X={new_x:.1f}, Y={new_y:.1f}, Z={new_z_offset:.2f}")

    def change_step(self):
        self.step_index = (self.step_index + 1) % len(MOVE_STEPS)
        logging.info(f"Step size set to {MOVE_STEPS[self.step_index]} mm")

    def get_current_bounds(self):
        experiment_name = self.dexarm.boundary_manager.current_experiment_name
        if experiment_name:
            return self.dexarm.boundary_manager.experiment_profiles.get(experiment_name)
        return None
    
    async def capture_environment(self):
        try:
            return await self.airq.get_conditions()
        except:
            return None, None

    async def run_single_cycle(self, cycle_index):
        """
        Executes one measurement cycle and guarantees that
        spectrometer data is persisted to HDF5.
        """

        cycle_data = {}

        # ---- HEADER ----
        if self.category == "long_term":
            logging.info(f"STARTING LONG-TERM MEASUREMENT: CYCLE {cycle_index + 1} / {self.lte_num_cycles}")
            logging.info("-" * 50)
        else:
            logging.info("STARTING EXPERIMENT")
            logging.info("-" * 50)

        # --- Environment START ---
        t_start, h_start = await self.capture_environment()
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cycle_data["times"] = {"start": start_time}
        cycle_data["airq"] = {
            "temp_start": t_start,
            "humid_start": h_start,
        }

        # --- Run Measurement ---
        await self.measurement_routine.start_goniometric_measurement()

        src = self.measurement_routine.experiment_data

        if not src or "spectrometer" not in src:
            logging.error(
                f"Cycle {cycle_index}: spectrometer data missing in measurement_routine.experiment_data"
            )
            if self.hdf5_manager:
                self.hdf5_manager.save_cycle_data(cycle_index, cycle_data)
            return

        # --- WRITE GLOBAL (ONCE) ---
        if self.hdf5_manager and not self.hdf5_manager._global_maps_written:
            self.hdf5_manager.write_experiment_bounds(
                bounds=self.experiment_data.get("experiment_bounds", {}),
                setup=src.get("experiment_setup", {}),
                global_maps=src.get("global_maps", {}),
                laser_source=self.measurement_routine.laser_source,
                lte_duration_min=self.lte_duration_min,
                lte_interval_min=self.lte_interval_min,
            )

        cycle_data["spectrometer"] = src["spectrometer"]

        # --- Environment END ---
        t_end, h_end = await self.capture_environment()
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cycle_data["times"]["end"] = end_time
        cycle_data["airq"].update(
            {
                "temp_end": t_end,
                "humid_end": h_end,
            }
        )

        if self.hdf5_manager:
            self.hdf5_manager.save_cycle_data(cycle_index, cycle_data)

            try:
                ServerAPIClient().upload_hdf5_file(
                    self.hdf5_manager.file_path,
                    self.hdf5_manager.exp_id,
                    self.hdf5_manager.fiber_id,
                    start_time,
                    end_time,
                )
            except Exception as e:
                logging.error(f"HDF5 upload failed: {e}")

    async def start(self):
        current_x, current_y, current_z = await self.dexarm.get_translated_position()
        self.x, self.y, self.z_offset = current_x, current_y, current_z - 300

        logging.info("Manual Control Mode")
        menu_str = "← → : X-axis | ↑ ↓ : Y-axis | W/S: Z-axis | C: Change step |R:Rotate | G: Manual Co-ord | " \
                   "X: Reset Boundary | I: Integration Time | A: Set Rotation step | " \
                   "B: Set Measurement step | Q: Quit" 
        
        logging.info(menu_str)
        logging.info(f"Step size: {MOVE_STEPS[self.step_index]} mm | Mode: {self.mode.upper()}")

        try:
            while True:
                key = await get_key()
                if not key:
                    await asyncio.sleep(0.01)
                    continue

                if key == "ENTER":
                    if self.category == "long_term":
                        if self.lte_duration_min <= 0 or self.lte_interval_min <= 0:
                            logging.warning("LTE configuration invalid. Returning to manual control.")
                            continue
                        
                        # --- LTE EXECUTION ---
                        total_duration_sec = self.lte_duration_min * 60
                        interval_sec = self.lte_interval_min * 60
                        start_time_lte = time.time()
                        cycle_count = 0
     
                        if self.hdf5_manager:
                            if 'pm400' not in self.experiment_data or not self.experiment_data['pm400'].get('history'):
                                self.experiment_data['pm400'] = {
                                    'final_setpoint': self.initial_laser_setpoint,
                                    'history': []
                                }
                                
                            # Bounds
                            bounds = self.get_current_bounds()
                            if bounds:
                                self.experiment_data['experiment_bounds'] = bounds
                            
                            self.hdf5_manager.save_global_setup(self.experiment_data)

                        while (time.time() - start_time_lte) < total_duration_sec:
                            cycle_start_time = time.time()
                            
                            # --- LOGGING CHANGE: Cycle 0/Total ---
                            logging.info(f"--- Starting LTE Cycle {cycle_count}/{self.lte_num_cycles} ---")
                            
                            if self.laser_control:
                                await self.laser_control.set_power(self.initial_laser_setpoint)

                            await self.run_single_cycle(cycle_count)
                            
                            if self.laser_control:
                                logging.info("Turning Laser ON for waiting period...")
                                await self.laser_control.set_power(self.initial_laser_setpoint)

                            cycle_count += 1
                            
                            elapsed = time.time() - cycle_start_time
                            sleep_time = interval_sec - elapsed
                            
                            # Check if next cycle fits
                            if (time.time() - start_time_lte + sleep_time) > total_duration_sec:
                                sleep_time = total_duration_sec - (time.time() - start_time_lte)
                                if sleep_time < 0: sleep_time = 0
                            
                            if sleep_time > 0:
                                logging.info(f"Cycle complete. Waiting {sleep_time/60:.2f} mins...")
                                await asyncio.sleep(sleep_time)
                            else:
                                if (time.time() - start_time_lte) < total_duration_sec:
                                    logging.info("Cycle took longer than interval, starting next immediately.")
                        
                        logging.info("LTE Experiment Finished.")
                        break

                    else:
                        # --- SINGLE EXECUTION ---
                        if self.hdf5_manager:
                            bounds = self.get_current_bounds()
                            if bounds: self.experiment_data['experiment_bounds'] = bounds
                            if 'pm400' not in self.experiment_data or not self.experiment_data['pm400'].get('history'):
                                self.experiment_data['pm400'] = {'final_setpoint': self.initial_laser_setpoint, 'history': []}
                            self.hdf5_manager.save_global_setup(self.experiment_data)

                        await self.run_single_cycle(0) # Cycle 0
                        logging.info("Single Experiment Finished.")
                        break

                # KEY HANDLING
                key = key.upper()
                if key == "LEFT": await self.move_by(dx=1)
                elif key == "RIGHT": await self.move_by(dx=-1)
                elif key == "UP": await self.move_by(dy=1)
                elif key == "DOWN": await self.move_by(dy=-1)
                elif key == "W": await self.move_by(dz=1)
                elif key == "S": await self.move_by(dz=-1)
                elif key == "C": self.change_step()
                elif key == "G": await self.manual_coord_move()
                elif key == "X":
                    self.limits_enabled = not self.limits_enabled
                    state = "enabled" if self.limits_enabled else "disabled"
                    logging.info(f"Boundary limits now {state}. Use 'H' to update.")
                elif key == "H":
                    if not self.limits_enabled:
                        await self.measurement_routine.reset_bounds()
                        self.limits_enabled = True
                        logging.info("Bounds updated and limits re-enabled.")
                    else: logging.info("Disable limits with 'X' before updating.")

                elif key == "M":
                    if self.spectrometer: await self.measurement_routine.take_single_spectrum()
                    else: logging.info("Spectrometer not initialized.")

                elif key == "R":
                    await self.measurement_routine.rotate_stage_manual()

                elif key == "P":
                    loop = asyncio.get_running_loop()
                    try:
                        power_str = await loop.run_in_executor(None, lambda: input("\nEnter laser power (mW): ").strip())
                        power_mw = float(power_str)
                        if self.laser_control:
                            await self.laser_control.set_power(power_mw)
                            logging.info(f"Laser power set to {power_mw} mW.")
                    except: logging.info("Invalid power input.")

                elif key == "I":
                    if self.spectrometer:
                        try:
                            logging.info(f"Current integration time: {self.spectrometer.integration_time_us} µs")
                            loop = asyncio.get_running_loop()
                            raw = await loop.run_in_executor(None, lambda: input("Enter new integration time (µs): ").strip())
                            if raw:
                                new_it = int(raw)
                                await self.spectrometer.set_integration_time(new_it)
                                logging.info(f"Time updated to {new_it} µs")
                        except: pass
                
                # --- A=Angular Steps & B =  Linear steps ---
                elif key == "B":
                    try:
                        loop = asyncio.get_running_loop()
                        current_step = self.measurement_routine.measurement_step_distance
                        print(f"\nCurrent Step Distance = {current_step}mm")
                        raw = await loop.run_in_executor(None, lambda: input("Enter the New Value = (or press enter to keep current): ").strip())
                        if raw: 
                            self.measurement_routine.measurement_step_distance = float(raw)
                            logging.info(f"Step distance updated to {raw}mm")
                    except: pass
                    
                elif key == "A":
                    try:
                        loop = asyncio.get_running_loop()
                        current_rot = self.measurement_routine.rotation_step
                        print(f"\nCurrent Angle Step = {current_rot}")
                        raw = await loop.run_in_executor(None, lambda: input("Enter the New Value = (or press enter to keep current): ").strip())
                        if raw: 
                            self.measurement_routine.rotation_step = float(raw)
                            logging.info(f"Rotation step updated to {raw}")
                    except: pass

                elif key == "Q":
                    await self.dexarm.sequential_home_zyx()
                    break

        except KeyboardInterrupt:
            logging.info("Manual control interrupted.")