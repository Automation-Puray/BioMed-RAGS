# Refactor/devices/laser_control.py
import serial
import asyncio
import logging
import json
import numpy as np
import functools


MAX_POWER_MW = 1050
MACROS = {'on': '7E02010101', 'off': '7E02010100'}


class LaserController:
    def __init__(self, port='/dev/ttyUSB1', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self._loop = asyncio.get_event_loop() # Get the current event loop

    async def _run_blocking(self, func, *args, **kwargs):
        """Helper to run blocking functions in a separate thread."""
        return await self._loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    
    async def connect(self):
        try:
            self.serial = await self._run_blocking(
                serial.Serial,
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            logging.info(f"Laser connected at {self.port}")
        except serial.SerialException as e:
            logging.error(f"Laser connection failed: {e}")
            self.serial = None
            return False


    async def send_command(self, hex_string):
        if not self.serial or not self.serial.is_open:
            logging.error("[Laser] Serial port is not open. Command not sent.")
            return
        try:
            data = bytes.fromhex(hex_string)
            await self._run_blocking(self.serial.write, data)
            await self._run_blocking(self.serial.flush)
            #logging.info(f"[Laser] Command sent: {hex_string} (bytes: {data.hex(' ').upper()})")
        except Exception as e:
            logging.error(f"Failed to send command: {e}")

    async def set_power(self, power_mw):
        if not (0 <= power_mw <= MAX_POWER_MW):
            logging.warning(f"Power must be between 0 and {MAX_POWER_MW} mW")
            return

        power_hex = f"{int(round(power_mw)):04X}"  # zero-padded HEX uppercase
        # Format command: start byte + length + command + power bytes
        hex_string = f"7E040102{power_hex[:2]}{power_hex[2:]}"
        #logging.info(f"[Laser] Setting laser power to {power_mw} mW (Command: {hex_string})")
        await self.send_command(hex_string)

        # Small delay to allow laser to process command
        await asyncio.sleep(0.1)

        if power_mw > 0:
            await self.turn_on()
        else:
            await self.turn_off()

    async def turn_on(self):
        #logging.info("[Laser] Turning ON")
        await self.send_command(MACROS['on'])

    async def turn_off(self):
        #logging.info("[Laser] Turning OFF")
        await self.send_command(MACROS['off'])

    async def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            logging.info("Serial connection closed.")

    async def safe_laser_transition(self):
        """Safe laser transition: power off and wait for fiber connection."""
        await self.set_power(0)
        logging.info("Laser calibrated and turned OFF for safety.")
        logging.info("Please now disconnect the laser from the power meter and connect the laser to the light diffusing fiber.")
        await self._run_blocking (input, "Press ENTER to confirm the fiber is connected and you are ready to proceed...")
        logging.info("Proceeding with the experiment.")


    async def ramp_power(self, target_mw, steps=5, delay=8):
        current = 0
        step = (target_mw - current) / steps
        for i in range(1, steps + 1):
            power_at_step = int(round(current + step * i))
            await self.set_power(power_at_step)
            await asyncio.sleep(delay)
