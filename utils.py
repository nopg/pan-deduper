import asyncio
import sys

from rich.pretty import pprint

import panorama_api
import settings


async def run(panorama: str, username: str, password: str):
    pa = panorama_api.Panorama_api(
        panorama=panorama, username=username, password=password
    )
    await pa.login()

    # Get Device Groups
    if not settings.device_groups:
        settings.device_groups = await pa.get_device_groups()

    pprint(settings.device_groups)

    for dg in settings.device_groups:
        print(f"\n----------{dg}-----------\n")
        # Get Address Objects
        addrs = await pa.get_address_objects(device_group=dg)

        # Get Address-Groups
        addr_groups = await pa.get_address_groups(device_group=dg)

        # Get Service Objects
        svcs = await pa.get_service_objects(device_group=dg)

        # Get Service-Groups
        svc_groups = await pa.get_service_groups(device_group=dg)

        pprint(addrs)
        pprint(addr_groups)
        pprint(svcs)
        pprint(svc_groups)