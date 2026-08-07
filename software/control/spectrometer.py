import os
import asyncio
import logging
import numpy as np
import json
import seabreeze.spectrometers as sb
from concurrent.futures import ThreadPoolExecutor

# SPECTROMETER Constants
FULL_SCALE          = 65535 # 16-bit ADC max for USB4000/Flame-T
SCANS_TO_AVERAGE    = 50
BOXSCAR             = 2
DEFAULT_INTEGRATION = 100000
T_INTEGRATION_MIN   = 3800
T_INTEGRATION_MAX   = 10000000
SATURATION_LIMIT    = 60000
SUBRANGE_MIN        = 200
SUBRANGE_MAX        = 500
SENSOR_AREA_CM2 = 0.11946 

class AsyncFlame:
    """
    Non-blocking wrapper for a SeaBreeze-compatible spectrometer (e.g., Flame, USB4000).
    Includes integration time control, dark reference storage, spectral calibration,
    saturation detection, and post-measurement spectrum integration.
    """

    def __init__(self, integration_time_us: int = DEFAULT_INTEGRATION):
        self.integration_time = integration_time_us
        self._dev = None
        self._dark = None
        self._wavelengths = None
        self._calibration = None
        self._pool = ThreadPoolExecutor(max_workers=1)

    # ---------- blocking helpers (run in executor) -------------------------
    def _sync_open(self):
        device_ids = sb.list_devices()
        if not device_ids:
            raise RuntimeError("No spectrometer found via SeaBreeze")
        
        self._dev = sb.Spectrometer(device_ids[0])
        self._dev.integration_time_micros(self.integration_time)
        logging.info(f"spectrometer: {device_ids[0]} open")
        for attr, arg in (("scans_to_average", SCANS_TO_AVERAGE), ("boxcar_width", BOXSCAR)):
            try:
                getattr(self._dev, attr)(arg)
            except AttributeError:
                pass

        self._dark = np.asarray(self._dev.intensities(), dtype=np.float32)
        self._wavelengths = np.asarray(self._dev.wavelengths(), dtype=np.float32)
        self._load_calibration()

    def _load_calibration(self, calib_path="/home/Biomed/fiber_gonio/calibration/9_FLMT09336_cc_20230822.IRRADCAL"):
        try:
            calib_data = np.loadtxt(calib_path, skiprows=9)
            calib_wl = calib_data[:, 0]
            calib_vals = calib_data[:, 1]
            self._calibration = np.interp(self._wavelengths, calib_wl, calib_vals)
            logging.info("Calibration data loaded and interpolated.")
        except Exception as e:
            logging.warning(f"Calibration file could not be parsed: {e}. Using flat calibration (ones). Results will not be accurate.")
            self._calibration = np.ones_like(self._wavelengths)

    def calibrate_spectrum(self, spectrum: np.ndarray) -> np.ndarray:
        if self._calibration is None:
            raise RuntimeError("Calibration not loaded.")
        if self._dark is None:
            raise RuntimeError("Dark spectrum not available.")
        if self._wavelengths is None:
            raise RuntimeError("Wavelengths not initialized.")

        # Step 1: Dark subtraction
        corrected = np.maximum(spectrum - self._dark, 0.0)
        # Step 2: Multiply by calibration factors (µJ/count/nm)
        calibrated = corrected * self._calibration
        # Step 3: Convert integration time from µs to s
        integration_time_s = self.integration_time / 1_000_000
        # Step 4: Divide by integration time and sensor area
        calibrated /= (integration_time_s * SENSOR_AREA_CM2) # FIX: Use module constant
        # Step 5: Divide by Δλ (nm), using mean spacing
        delta_lambda = np.mean(np.diff(self._wavelengths))
        calibrated /= delta_lambda

        return calibrated # Units: µW / cm² / nm

    def check_saturation(self, spectrum: np.ndarray, saturation_threshold: float = SATURATION_LIMIT) -> tuple[bool, float, float]:
        peak = float(np.max(spectrum))
        pct = 100.0 * peak / FULL_SCALE
        is_saturated = peak >= saturation_threshold
        return is_saturated, peak, pct

    async def capture_dark_reference(self):
        input("            INPUT:  Prepare to take Dark Spectrum, cover spectrometer and press ENTER")
        raw = await self.read_spectrum()
        self._dark = raw
        logging.info("Dark spectrum recorded")

    def integrate_spectrum(self, spectrum: np.ndarray, lower_nm: float = SUBRANGE_MIN, upper_nm: float = SUBRANGE_MAX) -> float:
        if self._wavelengths is None:
            raise RuntimeError("Wavelength array is not initialized.")
        if self._wavelengths.shape != spectrum.shape:
            raise ValueError("Wavelength and spectrum arrays must have the same shape.")

        mask = (self._wavelengths >= lower_nm) & (self._wavelengths <= upper_nm)
        if not np.any(mask):
            raise ValueError(f"No wavelengths found in range {lower_nm}–{upper_nm} nm.")

        return float(np.trapezoid(spectrum[mask], x=self._wavelengths[mask]))

    def _sync_acquire(self) -> np.ndarray:
        if self._dev is None:
            raise RuntimeError("Spectrometer device not initialized. Call open() first.")
        return np.asarray(self._dev.intensities(), dtype=np.float32)

    def _sync_close(self):
        if self._dev:
            self._dev.close()

    # ---------- async API ---------------------------------------------------
    
    async def open(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._pool, self._sync_open)

    async def read_spectrum(self) -> np.ndarray:
        if self._dev is None:
            raise RuntimeError("Spectrometer not opened. Did you forget to call await open()?")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._pool, self._sync_acquire)

    async def set_integration_time(self, us: int = DEFAULT_INTEGRATION):
        # Clamp integration time to device-supported range
        us = max(T_INTEGRATION_MIN, min(us, T_INTEGRATION_MAX))
        self.integration_time = us
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._pool, self._dev.integration_time_micros, us)

    async def close(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._pool, self._sync_close)
    
    async def save_session(self, session_json_path="/home/Biomed/fiber_gonio/calibration/session.json"):
        os.makedirs(os.path.dirname(session_json_path), exist_ok=True)
        session_data = {
            "integration_time_us": self.integration_time_us,
            "dark_path": session_json_path.replace(".json", "_dark.npy"),
            "calibration_path": session_json_path.replace(".json", "_calibration.npy"),
        }
        # Save JSON
        def _save_files():
            with open(session_json_path, "w") as f:
                json.dump(session_data, f, indent=2)
            if self._dark is not None:
                np.save(session_data["dark_path"], self._dark)
            if self._calibration is not None:
                np.save(session_data["calibration_path"], self._calibration)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _save_files)
        logging.info("Spectrometer session saved.")

    async def load_session(self, session_json_path="/home/Biomed/fiber_gonio/calibration/session.json"):
        def _load_files():
            try:
                with open(session_json_path, "r") as f:
                    session_data = json.load(f)
                self.integration_time = session_data.get("integration_time_us", DEFAULT_INTEGRATION)
                dark_path = session_data.get("dark_path")
                calib_path = session_data.get("calibration_path")
                if dark_path and os.path.exists(dark_path):
                    self._dark = np.load(dark_path)
                if calib_path and os.path.exists(calib_path):
                    self._calibration = np.load(calib_path)
                logging.info("Spectrometer session loaded.")
            except Exception as e:
                logging.warning(f"Failed to load spectrometer session: {e}")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _load_files)
        # Apply integration time to device if already open
        if self._dev is not None:
            await self.set_integration_time(self.integration_time)


    @property
    def wavelengths(self) -> np.ndarray:
        return self._wavelengths

    @property
    def integration_time_us(self) -> int:
        return self.integration_time
    
    @property
    def min_integration_time_us(self) -> int:
        """Exposes the minimum supported integration time in microseconds."""
        return T_INTEGRATION_MIN

    @property
    def max_integration_time_us(self) -> int:
        """Exposes the maximum supported integration time in microseconds."""
        return T_INTEGRATION_MAX
    
    @property # FIX: Changed from function to property
    def sensor_area_cm2(self) -> float:
        """Exposes the spectrometer sensor area."""
        return SENSOR_AREA_CM2