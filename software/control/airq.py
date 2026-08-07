import os

import aiohttp
from aioairq import AirQ


class AirQClient:
    def __init__(self, address=None, password=None):
        self.address = address or os.getenv("BIOMED_RAGS_AIRQ_ADDRESS")
        self.password = password or os.getenv("BIOMED_RAGS_AIRQ_PASSWORD")

    async def get_conditions(self):
        if not self.address or not self.password:
            raise RuntimeError(
                "Air-Q configuration is missing. Set "
                "BIOMED_RAGS_AIRQ_ADDRESS and BIOMED_RAGS_AIRQ_PASSWORD."
            )

        async with aiohttp.ClientSession() as session:
            airq = AirQ(self.address, self.password, session)
            data = await airq.get_latest_data()
            temperature = data.get("temperature")
            humidity = data.get("humidity")
            return temperature, humidity