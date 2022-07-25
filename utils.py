import asyncio
import sys
from itertools import product

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

    if settings.exclude_device_groups:
        for dg in settings.exclude_device_groups:
            settings.device_groups.remove(dg)

    print(f"Comparing these device groups:\n{settings.device_groups}")
    print(f"and these object types:\n{settings.to_dedupe}")

    coroutines = [list_duplicates(pa, object_type) for object_type in settings.to_dedupe]
    results = await asyncio.gather(*coroutines)

    print("Duplicates found: \n")
    pprint(results)


async def list_duplicates(pa, object_type):
    my_objs = {}
    for dg in settings.device_groups:
        if object_type == "addresses":
            objs = await pa.get_address_objects(device_group=dg)
        if object_type == "address-groups":
            objs = await pa.get_address_groups(device_group=dg)
        if object_type == "services":
            objs = await pa.get_service_objects(device_group=dg)
        if object_type == "service-groups":
            objs = await pa.get_service_groups(device_group=dg)

        if not objs:
            print(f"No {object_type} found, moving on...")
            return {object_type: []}
        my_objs[dg] = set([name["@name"] for name in objs])

    duplicates = compare_objects(my_objs)

    # print(f"\n\nDuplicate {object_type} found: [device-group names]:")
    # pprint(duplicates)

    results = {}
    results.setdefault(object_type, {})

    for dupe, dgs in duplicates.items():
        if len(dgs) >= settings.minimum_duplicates:
            #print(f"{dupe} equals or exceeds limit of {settings.minimum_duplicates} device group overlap!")
            results[object_type].update({dupe:dgs})
            #print(results)

    return results


def compare_objects(my_objects):
    duplicates = {}
    for items in product(my_objects, repeat=2):
        if items[0] == items[1]:
            continue
        dupes = my_objects[items[0]].intersection(my_objects[items[1]])

        for obj in dupes:
            if duplicates.get(obj):
                if items[0] not in duplicates[obj]:
                    duplicates[obj].append(items[0])
                if items[1] not in duplicates[obj]:
                    duplicates[obj].append(items[1])
            else:
                duplicates[obj] = list(items)

    return duplicates
