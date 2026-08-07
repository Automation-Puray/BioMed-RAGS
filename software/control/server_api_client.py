import logging
import os

import requests


def _server_api_url():
    url = os.getenv("BIOMED_RAGS_SERVER_API_URL", "").strip().rstrip("/")

    if not url:
        raise RuntimeError(
            "Server configuration is missing. "
            "Set BIOMED_RAGS_SERVER_API_URL."
        )

    if not url.startswith(("http://", "https://")):
        raise RuntimeError(
            "BIOMED_RAGS_SERVER_API_URL must start with http:// or https://."
        )

    return url


class ServerAPIClient:
    """Handles all API interactions with the remote server."""

    def get_fibers(self):
        try:
            response = requests.get(f"{_server_api_url()}/get_fibers.php")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Failed to get fiber list: {e}")
            return []

    def register_fiber(
        self,
        fiber_name,
        manufacturer=None,
        length_mm=None,
        core_diameter_um=None,
        coatings=None,
        material=None,
        remarks=None,
        connectorization=None,
    ):
        try:
            payload = {
                "fiber_name": fiber_name,
                "manufacturer": manufacturer or None,
                "length_mm": float(length_mm) if length_mm else None,
                "core_diameter_um": (
                    float(core_diameter_um) if core_diameter_um else None
                ),
                "coatings": coatings or None,
                "material": material or None,
                "remarks": remarks or None,
                "connectorization": connectorization or None,
            }
            response = requests.post(
                f"{_server_api_url()}/register_fiber.php",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Failed to register fiber: {e}")
            return None

    def get_catheters(self, fiber_id=None):
        try:
            response = requests.get(f"{_server_api_url()}/get_catheters.php")
            response.raise_for_status()
            catheters = response.json()

            if fiber_id is not None:
                catheters = [
                    catheter
                    for catheter in catheters
                    if catheter["fiber_id"] == fiber_id
                ]

            return catheters
        except Exception as e:
            logging.error(f"Failed to get catheter list: {e}")
            return []

    def register_catheter(
        self,
        cath_name,
        model=None,
        manufacturer=None,
        material=None,
        remarks=None,
    ):
        try:
            payload = {
                "cath_name": cath_name,
                "model": model or "",
                "manufacturer": manufacturer or "",
                "material": material or "",
                "remarks": remarks or "",
            }
            response = requests.post(
                f"{_server_api_url()}/register_catheter.php",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Failed to register catheter: {e}")
            return None

    def register_experiment(
        self,
        fiber_id,
        cath_id=None,
        laser_source=None,
        category="single",
    ):
        """
        Register an experiment.

        category: "single" or "long_term".
        """
        try:
            payload = {
                "fiber_id": int(fiber_id),
                "category": category,
            }

            if cath_id is not None:
                payload["cath_id"] = int(cath_id)

            if laser_source is not None:
                payload["laser_source"] = str(laser_source)

            response = requests.post(
                f"{_server_api_url()}/register_experiment.php",
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            return (
                result.get("exp_id"),
                result.get("fiber_exp_id"),
                result.get("exp_code"),
            )
        except Exception as e:
            logging.error(f"Failed to register experiment: {e}")
            return None

    def update_experiment_remarks(
        self,
        fiber_id,
        exp_id,
        final_observation,
    ):
        try:
            payload = {
                "fiber_id": fiber_id,
                "exp_id": exp_id,
                "final_observation": final_observation,
            }
            response = requests.post(
                f"{_server_api_url()}/update_experiment.php",
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("success", False)
        except requests.exceptions.HTTPError as e:
            logging.error(
                "HTTP error: %s - %s",
                e.response.status_code,
                e.response.text,
            )
            return False
        except Exception as e:
            logging.error(f"Failed to update final observation: {e}")
            return False

    def upload_hdf5_file(
        self,
        file_path,
        exp_id,
        fiber_id,
        start_time,
        end_time,
    ):
        """Upload an HDF5 file and its metadata to the server."""
        try:
            with open(file_path, "rb") as hdf5_file:
                files = {
                    "hdf5_file": (
                        file_path.split("/")[-1],
                        hdf5_file,
                        "application/octet-stream",
                    )
                }
                payload = {
                    "exp_id": exp_id,
                    "fiber_id": fiber_id,
                }

                if start_time:
                    payload["start_time"] = start_time

                if end_time:
                    payload["end_time"] = end_time

                logging.info(f"Attempting to upload file: {file_path}")

                response = requests.post(
                    f"{_server_api_url()}/upload_hdf5.php",
                    files=files,
                    data=payload,
                )
                response.raise_for_status()

                result = response.json()

                if result.get("success"):
                    logging.info(
                        "HDF5 file uploaded successfully. Path: %s",
                        result.get("path"),
                    )
                    return True

                logging.error(
                    "Server indicated failure: %s",
                    result.get("message"),
                )
                return False

        except requests.exceptions.HTTPError as e:
            logging.error(
                "HTTP error during upload: %s - %s",
                e.response.status_code,
                e.response.text,
            )
            return False
        except FileNotFoundError:
            logging.error(f"HDF5 file not found at path: {file_path}")
            return False
        except Exception as e:
            logging.error(f"Failed to upload HDF5 file: {e}")
            return False