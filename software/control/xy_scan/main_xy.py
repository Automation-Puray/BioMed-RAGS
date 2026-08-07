import asyncio
import logging
import sys
import os

# 1. Setup path to include the parent 'devices' folder
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
project_root_dir = os.path.dirname(parent_dir)
sys.path.append(project_root_dir)

from Refactor.devices.dexarm_controller import DexArmController
from Refactor.devices.spectrometer import AsyncFlame

from Refactor.devices.xy_scan.xy_hdf5_manager import XYHDF5Manager
from Refactor.devices.xy_scan.manual_xy import ManualXYController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)-7s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)

async def main():

    dexarm = DexArmController()
    try:
        await dexarm.initialize()
    except Exception as e:
        logging.error(f"Robot Init Failed: {e}")
        return

    spectrometer = AsyncFlame()
    try:
        await spectrometer.open()
        logging.info("Spectrometer Connected.")
    except Exception as e:
        logging.error(f"Spectrometer Init Failed: {e}")
        spectrometer = None

    print("\n--- Experiment Setup ---")
    loop = asyncio.get_running_loop()
    exp_name = await loop.run_in_executor(
        None, lambda: input("Enter Experiment Name (e.g. test): ").strip()
    )
    if not exp_name:
        exp_name = "test_experiment"

    hdf5_manager = XYHDF5Manager(experiment_name=exp_name)
    hdf5_path = hdf5_manager.create_file()

    if hdf5_path and spectrometer:
        hdf5_manager.write_spectrometer_metadata(
            spectrometer.integration_time_us,
            spectrometer.sensor_area_cm2
        )

    controller = ManualXYController(dexarm, spectrometer, hdf5_manager)

    try:
        await controller.start()
    finally:
        if hdf5_manager:
            hdf5_manager.close()
        if spectrometer:
            await spectrometer.close()
        await dexarm.close()
        print("Application Closed.")

if __name__ == "__main__":
    asyncio.run(main())
