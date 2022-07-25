import asyncio
import sys
from itertools import product

from lxml import etree
from rich.pretty import pprint

import panorama_api
import settings


def run_xml(configstr):
    config = etree.fromstring(configstr)

    # Get Device Groups
    if not settings.device_groups:
        dgs = config.find("devices/entry[@name='localhost.localdomain']/device-group")
        for entry in dgs.getchildren():
            settings.device_groups.append(entry.get("name"))

    if settings.exclude_device_groups:
        for dg in settings.exclude_device_groups:
            settings.device_groups.remove(dg)

    pprint(settings.device_groups)

    results = []
    for object_type in settings.to_dedupe:
        results.append(get_duplicates_xml(config, object_type))

    print("Duplicates found: \n")
    pprint(results)


def get_duplicates_xml(config, object_type):
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

    print(f"Comparing these device groups:\n\t{settings.device_groups}")
    print(f"and these object types:\n\t{settings.to_dedupe}")

    coroutines = [get_duplicates(pa, object_type) for object_type in settings.to_dedupe]
    results = await asyncio.gather(*coroutines)

    print("Duplicates found: \n")
    pprint(results)


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
