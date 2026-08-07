# devices/arduino_stage.py

import serial
import logging
import asyncio
# ARDUINO - Rotational Stage
SERIAL_PORT_ARDUINO = '/dev/ttyUSB0'
BAUD_RATE_ARDUINO = 115200

class ArduinoStage:
    def __init__(self, port=SERIAL_PORT_ARDUINO, baudrate=BAUD_RATE_ARDUINO):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    async def connect(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=2
            )
            logging.info(f"arduino: {self.port} open")
            return True
        except serial.SerialException as e:
            logging.error(f"✗  Error opening serial port {self.port}: {e}")
            self.ser = None
            return False

    async def send_angle(self, angle: float):
        if self.ser is None:
            logging.error("Arduino serial port not open!")
            return
        try:
            # Use threadsafe sync call
            command = f"{int(angle)}\n"
            await asyncio.to_thread(self.ser.write, command.encode('utf-8'))
            await asyncio.to_thread(self.ser.flush)
            logging.debug(f"→ Sent to Arduino: {angle}°")
        except Exception as e:
            logging.error(f"Failed to send to Arduino: {e}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            logging.info(f"Arduino: {self.port} closed.")
