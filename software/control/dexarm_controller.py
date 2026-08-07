# /home/Biomed/fiber_gonio/Refactor/devices/dexarm_controller.py
import os
import logging
import asyncio 
import functools
from DexArm_API.pydexarm import Dexarm
from Refactor.devices.robot_limits import RobotBoundaryManager, CALIBRATION_JSON_PATH

DEFAULT_DEXARM_PORT = "/dev/ttyACM0"

def unpack_xyz(raw):
    """
    DexArm returns (x, y, z, e, a, b, c)
    User coords:
    - X = E  (DexArm extrusion axis)
    - Y = Z  (DexArm vertical axis)
    - Z = Y  (DexArm sliding rail axis)
    """
    return raw[3], raw[2], raw[1]

def pack_xyz(x, y, z):
    """
    Convert user coords to DexArm internal coords:
    - e = X (left/right)
    - z = Y (up/down)
    - y = Z (forward/back)
    """
    return {"e": x, "y": z, "z": y}

class DexArmController:
    def __init__(self, port=DEFAULT_DEXARM_PORT, config_path=CALIBRATION_JSON_PATH):
        self.dex = Dexarm(port)
        self.boundary_manager = RobotBoundaryManager(config_path)

        if self.dex.is_open:
            logging.info(f"DexArm serial port established: {port}")
        else:
            logging.error(f"Failed to open DexArm serial port: {port}")
    
    async def _run_blocking(self, func, *args, **kwargs):
        """Helper to run blocking pydexarm methods in a separate thread."""
        loop = asyncio.get_running_loop()
        # Use functools.partial to create a callable that can be executed by the executor
        return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    
    async def initialize(self):
        #logging.info("Initializing sliding rail...")
        await self._run_blocking(self.dex.sliding_rail_init)
        await asyncio.sleep(3)

        #logging.info("Homing DexArm...")
        await self.home_dexarm()
        await asyncio.sleep(2)

        #logging.info("Setting work origin...")
        await self._run_blocking(self.dex.set_workorigin)
        logging.info("DexArm initialized.")

    

    async def home_dexarm(self):
        #logging.info("Homing DexArm and resetting X (e=0)...")
        await self._run_blocking(self.dex.go_home)
        await self._run_blocking(self.dex.move_to, e=0)

    def set_experiment(self, name: str):
        self.boundary_manager.set_experiment(name)
        #logging.info(f"Experiment bounds loaded: {name}")

    async def move_to(self, x=None, y=None, z=None, feedrate=2000,partial=False):
        coords = pack_xyz(x, y, z)
        await self._run_blocking(self.dex.move_to, **coords, feedrate=feedrate)
        if not partial:
            
            logging.info(f"Moved to : x={x}, y={y}, z={z}")

    async def fast_move_to(self, x=None, y=None, z=None, feedrate=3000):
        coords = pack_xyz(x, y, z)
        await self._run_blocking(self.dex.fast_move_to, **coords, feedrate=feedrate)
        logging.info(f"Fast moved to (user coords): x={x}, y={y}, z={z}")
        

    async def safe_move_to(self, x=None, y=None, z=None, feedrate=2000,partial=False, safety_override=False):
        current = await self.get_translated_position()
        target_x = x if x is not None else current[0]
        target_y = y if y is not None else current[1]
        target_z = z if z is not None else (current[2] - 300.0)
        

        if (not safety_override) and (not self.boundary_manager.is_position_safe(target_x, target_y, target_z)):
            logging.warning("Unsafe target position. Moving to SAFE_PARK_COORDINATES.")
            coords = self.boundary_manager.get_safe_park_coordinates()
            sx, sy, sz = coords['x'], coords['y'], coords['z']
            sx, sy, sz = float(sx), float(sy), float(sz)
            await self.move_to(x=sx, y=sy, z=sz)
            return False

        await self.move_to(x=x, y=y, z=z, feedrate=feedrate,partial=partial)
        return True

    async def get_position(self):
        pos = await self._run_blocking(self.dex.get_current_position)
        logging.info(f"Current DexArm position (raw): {pos}")
        return pos

    async def get_translated_position(self):
        raw = await self._run_blocking(self.dex.get_current_position)
        x, y, z = unpack_xyz(raw)
        #logging.info(f"Translated position (Robot coords): x={x}, y={y}, z={z}")
        return x, y, z


    async def sequential_move_xyz(self, x=None, y=None, z=None, feedrate=2000, safety_override=False):
        #logging.info(f"Sequentially moving to: x={x}, y={y}, z={z}")

        # Step 1: Move X-axis (keep other targets unchanged)
        if x is not None:
            if not await self.safe_move_to(x=x, y=None, z=None, feedrate=feedrate, partial=True, safety_override=safety_override):
                return False
            await asyncio.sleep(1)

        # Step 2: Move Y-axis
        if y is not None:
            if not await self.safe_move_to(x=x, y=y, z=None, feedrate=feedrate, partial=True, safety_override=safety_override):
                return False
            await asyncio.sleep(1)

        # Step 3: Move Z-axis
        if z is not None:
            if not await self.safe_move_to(x=x, y=y, z=z, feedrate=feedrate, safety_override=safety_override):
                return False
            await asyncio.sleep(1)

        return True


    async def move_to_experiment_entry(self, x=None, y=None, z=None, feedrate=2000):
        """
        Move from outside the experiment envelope into the experiment start point.

        Intermediate waypoints are checked only against HARD limits so the robot
        can travel from Home into the saved experiment boundary.

        The final target must still satisfy the normal experiment safety check.
        """
        current_x, current_y, current_z_raw = await self.get_translated_position()
        current_z_offset = current_z_raw - 300.0

        target_x = x if x is not None else current_x
        target_y = y if y is not None else current_y
        target_z = z if z is not None else current_z_offset

        # Final target must still be fully safe:
        # hard limits + experiment bounds
        if not self.boundary_manager.is_position_safe(target_x, target_y, target_z):
            logging.warning(
                f"Experiment start position is unsafe: x={target_x}, y={target_y}, z={target_z}"
            )
            coords = self.boundary_manager.get_safe_park_coordinates()
            sx, sy, sz = float(coords["x"]), float(coords["y"]), float(coords["z"])
            await self.move_to(x=sx, y=sy, z=sz)
            return False

        # Step 1: Move X using HARD limits only
        if x is not None:
            if not self.boundary_manager.is_within_hard_limits(target_x, current_y, current_z_offset):
                logging.warning(
                    f"Experiment entry X-step violates hard limits: "
                    f"x={target_x}, y={current_y}, z={current_z_offset}"
                )
                return False

            await self.move_to(x=x, y=None, z=None, feedrate=feedrate, partial=True)
            await asyncio.sleep(1)
            current_x = target_x

        # Step 2: Move Y using HARD limits only
        if y is not None:
            if not self.boundary_manager.is_within_hard_limits(current_x, target_y, current_z_offset):
                logging.warning(
                    f"Experiment entry Y-step violates hard limits: "
                    f"x={current_x}, y={target_y}, z={current_z_offset}"
                )
                return False

            await self.move_to(x=x, y=y, z=None, feedrate=feedrate, partial=True)
            await asyncio.sleep(1)
            current_y = target_y

        # Step 3: Move Z using HARD limits only
        if z is not None:
            if not self.boundary_manager.is_within_hard_limits(current_x, current_y, target_z):
                logging.warning(
                    f"Experiment entry Z-step violates hard limits: "
                    f"x={current_x}, y={current_y}, z={target_z}"
                )
                return False

            await self.move_to(x=x, y=y, z=z, feedrate=feedrate)
            await asyncio.sleep(1)

            return True

    

    async def sequential_home_zyx(self, feedrate=2000):
    
        #logging.info("Starting sequential homing: Z -> Y -> X")

        # Get the current position to maintain other axis values during movement
        current_x, current_y, _ = await self.get_translated_position()

        await self.move_to(x=current_x, y=current_y, z=-100, feedrate=feedrate,partial=True)
        
        await self.move_to(x=current_x, y=0, z=-100, feedrate=feedrate,partial=True)
    
        await self.move_to(x=0, y=0, z=-100, feedrate=feedrate)
        


    async def delay(self, ms=1000):
        await self._run_blocking(self.dex.dealy_ms, ms)

    async def close(self):
        await self._run_blocking(self.dex.close) 
        logging.info("DexArm connection closed.")
