import asyncio
import logging
from Refactor.devices.manual_control import ManualDexArmController, get_key
from .xy_scanner import XYScanRoutine

ADC_MAX = 65535.0

class ManualXYController(ManualDexArmController):
    def __init__(self, dexarm, spectrometer, hdf5_manager, **kwargs):
        super().__init__(dexarm, spectrometer=spectrometer, hdf5_manager=hdf5_manager, **kwargs)
        self.xy_routine = XYScanRoutine(dexarm, spectrometer, hdf5_manager)

    async def start(self):
        cx, cy, cz = await self.dexarm.get_translated_position()
        self.x, self.y, self.z_offset = cx, cy, cz - 300

        logging.info("Manual XY Controller Keys.")
        logging.info(" [ENTER] : Configure & Start XY Scan")
        logging.info(" [D]     : Capture Dark Spectrum")
        logging.info(" [I]     : Set Integration Time")
        logging.info(" [M]     : Measure Spectrum")
        logging.info(" [G]     : Coordinate Move")
        logging.info(" [Arrows/WS] : Manual Jog Robot")
        logging.info(" [Q]     : Quit")

        try:
            while True:
                key = await get_key()
                if not key:
                    await asyncio.sleep(0.01)
                    continue

                if key == "ENTER":
                    configured = await self.xy_routine.configure()

                    if not configured:
                        logging.warning(
                            "XY scan configuration failed; scan was not started."
                        )
                        continue

                    loop = asyncio.get_running_loop()
                    confirm = await loop.run_in_executor(
                        None,
                        lambda: input("Start Scan? (y/n): ").strip().lower(),
                    )

                    if confirm == "y":
                        await self.xy_routine.run()
                    else:
                        logging.info("Scan cancelled.")

                    continue

                key = key.upper()

                if key == "D":
                    if self.spectrometer:
                        print("\nTurn OFF the source and press ENTER to capture Dark Spectrum.")
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, lambda: input())
                        dark = await self.spectrometer.read_spectrum()
                        self.hdf5_manager.save_dark_spectrum(dark)
                        
                elif key == "C": 
                    self.change_step()

                elif key == "M":
                    if self.spectrometer:
                        spec = await self.spectrometer.read_spectrum()
                        peak = float(max(spec))
                        saturation = (peak / ADC_MAX) * 100.0
                        logging.info(
                            f"Sample captured | Peak: {peak:.0f} | "
                            f"Saturation: {saturation:.2f}%"
                        )

                elif key == "I":
                    if self.spectrometer:
                        print(f"Current Int Time: {self.spectrometer.integration_time_us} us")
                        loop = asyncio.get_running_loop()
                        val = await loop.run_in_executor(
                            None, lambda: input("New Int Time (us): ").strip()
                        )
                        if val.isdigit():
                            await self.spectrometer.set_integration_time(int(val))
                            self.hdf5_manager.write_spectrometer_metadata(
                                int(val),
                                self.spectrometer.sensor_area_cm2
                            )
                            logging.info("Integration time updated.")

                elif key == "G":
                    await self.manual_coord_move()

                elif key in ["LEFT", "RIGHT", "UP", "DOWN", "W", "S"]:
                    dx = dy = dz = 0
                    if key == "LEFT": dx = 1
                    elif key == "RIGHT": dx = -1
                    elif key == "UP": dy = 1
                    elif key == "DOWN": dy = -1
                    elif key == "W": dz = 1
                    elif key == "S": dz = -1
                    await self.move_by(dx, dy, dz)

                elif key == "Q":
                    await self.dexarm.sequential_home_zyx()
                    logging.info("Exiting...")
                    break

        except KeyboardInterrupt:
            logging.info("Interrupted.")
