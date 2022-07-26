import asyncio
import sys
from itertools import combinations

from lxml import etree
from rich.pretty import pprint

from panorama_api import Panorama_api
import settings


async def get_duplicates_xml(config, object_type):
    my_objs = {}
    for dg in settings.device_groups:
        if object_type == "addresses":
            objs = config.xpath(
                f"//devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/address/entry"
            )
        if object_type == "address-groups":
            objs = config.xpath(
                f"//devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/address-group/entry"
            )
        if object_type == "services":
            objs = config.xpath(
                f"//devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/service/entry"
            )
        if object_type == "service-groups":
            objs = config.xpath(
                f"//devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/service-group/entry"
            )

        if not objs:
            print(f"No {object_type} found, moving on...")
            return {object_type: []}

        my_objs[dg] = set([name.get("name") for name in objs])

    duplicates = find_duplicates(my_objs)

    results = {}
    results[object_type] = {}

    for dupe, dgs in duplicates.items():
        if len(dgs) >= settings.minimum_duplicates:
            results[object_type].update({dupe: dgs})

    return results

async def get_duplicates(pa, object_type):
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

    duplicates = find_duplicates(my_objs)

    results = {}
    results[object_type] = {}

    for dupe, dgs in duplicates.items():
        if len(dgs) >= settings.minimum_duplicates:
            results[object_type].update({dupe: dgs})

    return results


def find_duplicates(my_objects):
    duplicates = {}
    for items in combinations(my_objects, r=2):
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


async def set_device_groups(*, config = None, pan: Panorama_api = None):
    if config:
        if not settings.device_groups:
            dgs = config.find("devices/entry[@name='localhost.localdomain']/device-group")
            for entry in dgs.getchildren():
                settings.device_groups.append(entry.get("name"))
    else:
        if not settings.device_groups:
            settings.device_groups = await pan.get_device_groups()

    if settings.exclude_device_groups:
        for dg in settings.exclude_device_groups:
            settings.device_groups.remove(dg)

    print(f"Comparing these device groups:\n\t{settings.device_groups}")
    print(f"and these object types:\n\t{settings.to_dedupe}")


async def run(*, configstr: str = None, panorama: str = None, username: str = None, password: str = None):
    if configstr:
        config = etree.fromstring(configstr)
        await set_device_groups(config=config)
        coroutines = [get_duplicates_xml(config, object_type) for object_type in settings.to_dedupe]

    else:
        pan = Panorama_api(
            panorama=panorama, username=username, password=password
        )
        await pan.login()
        await set_device_groups(pan=pan)
        coroutines = [get_duplicates(pan, object_type) for object_type in settings.to_dedupe]

    results = await asyncio.gather(*coroutines)

    print("Duplicates found: \n")
    pprint(results)

