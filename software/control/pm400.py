import logging
import json
import time
import asyncio
import functools
from Refactor.devices.laser_control import MAX_POWER_MW


# Adjustable parameters for feedback
TOLERANCE_MW = 20
RAMP_DELAY_SEC = 10
STEP_DELAY_SEC = 10
FINAL_DELAY_SEC = 5
MAX_ATTEMPTS = 3


class PM400:
    def __init__(self, resource_str, visa_rm):
        self.resource_str = resource_str
        self.visa_rm = visa_rm
        self.inst = None
        self._loop = asyncio.get_event_loop()

    async def _run_blocking(self, func, *args, **kwargs):
        """Helper to run blocking functions in a separate thread."""
        return await self._loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    async def connect(self):
        try:
            self.inst = await self._run_blocking(self.visa_rm.open_resource, self.resource_str)
            idn_response = await self._run_blocking(self.inst.query, "*IDN?")
            logging.info("PM400 connected: " + idn_response.strip())
            return True
        except Exception as e:
            logging.error(f"Failed to connect to PM400: {e}")
            self.inst = None
            return False

    async def get_power_mw(self):
        if self.inst is None:
            return None
        try:
            result_str = await self._run_blocking(self.inst.query, "MEAS:POW?")
            result = float(result_str) * 1000
            #logging.info(f"[PM400] Measured power: {result:.2f} mW")
            return result
        except Exception as e:
            logging.error(f"PM400 read failed: {e}")
            return None

    async def close(self):
        if self.inst is not None:
            self.inst.close()  # no await
            logging.info("PM400 connection closed.")

    async def feedback_control(self, laser, target_mw, calibration_path):
        logging.info(f"[PM400] Starting feedback loop to reach {target_mw} mW")

        with open(calibration_path, 'r') as f:
            data = json.load(f)

        calibration = sorted([(d['Setpoint (mW)'], d['Measured (mW)']) for d in data], key=lambda x: x[1])
        setpoints, measured_outputs = zip(*calibration)

        closest_idx = min(range(len(measured_outputs)), key=lambda i: abs(measured_outputs[i] - target_mw))
        sp_start = int(round(setpoints[closest_idx]))
        #logging.info(f"[PM400] Nearest calibration setpoint to {target_mw} mW is {sp_start} mW")

        history = []

        # Turn laser off initially for safety
        await laser.set_power(0)
        await asyncio.sleep(RAMP_DELAY_SEC)

        # Ramp up to start setpoint in 5 steps
        ramp_steps = 5
        for i in range(1, ramp_steps + 1):
            ramp_power = int(round(sp_start * i / ramp_steps))
            await laser.set_power(ramp_power)
            await asyncio.sleep(RAMP_DELAY_SEC)
            measured = await self.get_power_mw()
            if measured is not None:
                history.append((ramp_power, measured))

        # Feedback loop
        for attempt in range(MAX_ATTEMPTS):
            await laser.set_power(sp_start)
            #logging.info(f"[PM400] Attempt {attempt + 1}: setting laser to {sp_start} mW")
            await asyncio.sleep(STEP_DELAY_SEC)
            measured = await self.get_power_mw()
            if measured is None:
                logging.warning("Measurement failed. Retrying...")
                continue

            history.append((sp_start, measured))
            error = target_mw - measured
            #logging.info(f"[PM400] Measured {measured:.2f} mW, Error = {error:.2f} mW")

            if abs(error) <= TOLERANCE_MW:
                await asyncio.sleep(FINAL_DELAY_SEC)
                final_check = await self.get_power_mw()
                if final_check is not None and abs(target_mw - final_check) <= TOLERANCE_MW:
                    logging.info(f"[PM400] Target achieved with final check: {final_check:.2f} mW")
                    return sp_start, final_check, history

            sp_start += 1 if error > 0 else -1
            sp_start = max(0, min(sp_start, MAX_POWER_MW))

        logging.warning("Failed to reach target power within tolerance.")
        return sp_start, measured, history
