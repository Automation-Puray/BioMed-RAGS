# /home/Biomed/fiber_gonio/Refactor/devices/spectro_optimizer.py
import asyncio
import logging
import numpy as np

# Import constants from the spectrometer module
from Refactor.devices.spectrometer import AsyncFlame, FULL_SCALE, T_INTEGRATION_MIN
from Refactor.devices.dexarm_controller import DexArmController
from Refactor.devices.laser_control import LaserController

# Target saturation parameters
TARGET_SATURATION = 0.80  # Target 88% #default value 80%
SATURATION_TOLERANCE = 0.05 # +/- 3%, so 85%-91% is acceptable #default value 0.05
MAX_OPTIMIZATION_ATTEMPTS = 50


class SpectrometerOptimizer:
    """
    Handles the live optimization of spectrometer integration time 
    for Continuous Wave (CW) measurements.
    """
    
    def __init__(self, spectrometer: AsyncFlame, dexarm: DexArmController, laser_control: LaserController):
        self.spectrometer = spectrometer
        self.dexarm = dexarm
        self.laser_control = laser_control

    async def _find_optimal_time_live(self, seed_time_us: int) -> tuple[np.ndarray, int, float]:
        """
        Iteratively adjusts the integration time to target ~85-91% of saturation.

        The 'seed_time_us' is the optimal time from the previous measurement point.

        Returns: (spectrum, optimal_time_us, saturation_pct)
        saturation_pct is returned as a percentage (0-100) to match existing logs.
        """
        current_time_us = max(seed_time_us, T_INTEGRATION_MIN)

        FULL_SCALE_FLOAT = float(FULL_SCALE)
        TARGET_COUNT = FULL_SCALE_FLOAT * TARGET_SATURATION

        #logging.info(f"   Optimization started with IntT={current_time_us}us") #commented due to too much logging

        # Initialize to zero arrays in case of immediate failure
        raw_signal = np.zeros(len(self.spectrometer.wavelengths) if hasattr(self.spectrometer, "wavelengths") else 3648) 
        saturation_pct = 0.0

        # safety caps for step changes
        MAX_GROWTH_FACTOR = 10.0  # don't try to increase time by more than 10x in one iteration
        MIN_CHANGE_FACTOR = 1.10  # if rounding prevents a change, force at least 10% change

        for attempt in range(MAX_OPTIMIZATION_ATTEMPTS):
            try:
                # 1. Set time and acquire signal
                await self.spectrometer.set_integration_time(current_time_us)
                raw_signal = await self.spectrometer.read_spectrum()

                # 2. Check saturation
                is_saturated, peak_count, saturation_pct = self.spectrometer.check_saturation(raw_signal)

                # Normalize saturation to fraction for internal logic (handle % vs fraction)
                # If check_saturation returns e.g. 4.5 (percent), we convert to 0.045
                if saturation_pct is None:
                    saturation_frac = 0.0
                elif saturation_pct > 1.0:
                    saturation_frac = float(saturation_pct) / 100.0
                else:
                    saturation_frac = float(saturation_pct)

                logging.debug(f"Attempt {attempt+1}: Peak={peak_count:.0f} | Saturation={saturation_frac*100:.2f}% (raw={saturation_pct})")

                # 3. Check for target hit (use fraction)
                if abs(saturation_frac - TARGET_SATURATION) <= SATURATION_TOLERANCE:
                    logging.info(
                        f"Captured: Peak={int(peak_count)} | "
                        f"{saturation_frac*100:.1f}% | "
                        f"IntT={current_time_us}us"
                    )
                    return raw_signal, current_time_us, saturation_frac * 100.0

                # 4. Calculate suggested new time
                if peak_count <= 0:
                    # no signal, increase decently
                    suggested_time = current_time_us * 2
                else:
                    # scale linearly based on counts toward the target count
                    multiplier = TARGET_COUNT / max(1.0, float(peak_count))
                    # cap extreme multipliers
                    multiplier = min(multiplier, MAX_GROWTH_FACTOR)
                    suggested_time = int(current_time_us * multiplier)

                # If suggested_time equals current_time_us (due to rounding), force a change:
                if suggested_time == current_time_us:
                    if saturation_frac < (TARGET_SATURATION - SATURATION_TOLERANCE):
                        # below target: increase by at least MIN_CHANGE_FACTOR
                        suggested_time = int(max(current_time_us * MIN_CHANGE_FACTOR, current_time_us + 1))
                    else:
                        # above target: decrease by 10%
                        suggested_time = int(max(current_time_us * 0.9, 1))

                # 5. Apply direction logic safely
                if is_saturated or saturation_frac > (TARGET_SATURATION + SATURATION_TOLERANCE):
                    # too high -> decrease (but don't accidentally increase)
                    if suggested_time < current_time_us:
                        new_time = suggested_time
                    else:
                        new_time = int(current_time_us * 0.9)
                    if is_saturated:
                        logging.warning(" Adjusting integration time.")
                else:
                        # too low -> increase
                    new_time = suggested_time

                # Enforce limits from spectrometer
                new_time = max(new_time, T_INTEGRATION_MIN)
                new_time = min(new_time, getattr(self.spectrometer, "max_integration_time_us", new_time))

                # If new_time didn't change because of clipping, try a minimal safe step
                if new_time == current_time_us:
                    if saturation_frac < TARGET_SATURATION:
                        new_time = min(int(current_time_us * MIN_CHANGE_FACTOR), getattr(self.spectrometer, "max_integration_time_us", current_time_us))
                    else:
                        new_time = max(int(current_time_us * 0.9), T_INTEGRATION_MIN)

                # Prepare for next attempt
                current_time_us = int(new_time)

                # Final attempt handling
                if attempt == MAX_OPTIMIZATION_ATTEMPTS - 1:
                    logging.warning(
                        f"Optimization did not fully converge "
                        f"(Final: {saturation_frac*100:.1f}%, IntT={current_time_us}us)"
                    )
                    return raw_signal, current_time_us, saturation_frac * 100.0

            except Exception as e:
                logging.error(f"Optimization error: {e}")
                # Use current values as fallback before breaking the loop
                return raw_signal, current_time_us, saturation_pct

        # Fallback (shouldn't reach here)
        return raw_signal, current_time_us, saturation_pct


    async def run_live_measurement_point(self, x_pos: float, y_pos: float, z_pos: float, seed_time_us: int) -> dict:
        """
        Moves the robot to a point, performs live auto-exposure, and returns the result.
        No laser control is performed here (CW mode).
        """
        x_pos_rounded = round(x_pos, 1)
        
        try:
            # 1. Move to position
            logging.info(f"Measure: X={x_pos_rounded}mm")
            await self.dexarm.sequential_move_xyz(x=x_pos, y=y_pos, z=z_pos)
            await asyncio.sleep(2) # Wait for robot to settle

            # 2. Find optimal integration time (Signal Acquisition)
            raw_signal, optimal_time, saturation_pct = await self._find_optimal_time_live(seed_time_us)
            
            # Log the captured signal peak
            logging.info(f"Data captured: X={x_pos_rounded}mm | Signal Peak={np.max(raw_signal):.0f} | IntT={optimal_time}us")

            # 3. Compile result
            return {
                "spectrum": raw_signal,
                "integration_time": optimal_time,
                "x_position": x_pos,
                "saturation_pct": saturation_pct
            }

        except Exception as e:
            logging.error(f"Error during acquisition at X={x_pos_rounded}mm: {e}")
            # Return zeros/defaults on failure
            return {
                "spectrum": np.zeros(3648),
                "integration_time": seed_time_us,
                "x_position": x_pos,
                "saturation_pct": 0.0
            }