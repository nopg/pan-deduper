import asyncio
import importlib.resources as pkg_resources
import importlib.util
import json
import logging
import sys
from datetime import datetime
from itertools import combinations
from typing import Any, Dict, List

from lxml import etree
from lxml.etree import XMLSyntaxError
from rich.pretty import pprint

from pan_deduper.panorama_api import Panorama_api

# Logging setup:
logger = logging.getLogger("utils")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
try:
    file_handler = logging.FileHandler("deduper.log")
except PermissionError:
    print("Permission denied creating deduper.log, check folder permissions.")
    sys.exit(1)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Import 'settings' at runtime
# First time/one-time creation of a default settings.py for user
try:
    spec = importlib.util.spec_from_file_location("settings", "./settings.py")
    settings = importlib.util.module_from_spec(spec)
    sys.modules["settings"] = settings
    spec.loader.exec_module(settings)

except (FileNotFoundError, ImportError, ModuleNotFoundError):
    print("------------------------------------")
    print("\nThanks for using PAN Deduper...")
    print("settings.py not found!")
    print("We assume this is your first time..\n")
    print("------------------------------------")
    settingsfile = pkg_resources.read_text("pan_deduper", "settings.py")
    try:
        with open("settings.py", "w") as f:
            f.write(settingsfile)
    except IOError as e:
        print("Error creating settings.py in local directory, permissions issue?")
        sys.exit(1)
    print(
        "Default settings created in local directory, please review 'settings.py' and run again.\n"
    )
    sys.exit(0)


async def run_deduper(
    *,
    configstr: str = None,
    panorama: str = None,
    username: str = None,
    password: str = None,
    deep: bool = False
) -> None:
    """
    Main program - BEGIN!

    Args:
        configstr:  xml config file string
        panorama:   panorama IP/FQDN
        username:   panorama username
        password:   panorama password
    Returns:
        N/A

    Raises:
        N/A
    """
    logger.info("")
    logger.info("----Running deduper---")
    logger.info("")

    my_objs = []

    print("\n\tGetting...\n")
    if configstr:
        my_objs = await get_objects_xml(configstr, deep)

    elif panorama:
        pan = Panorama_api(panorama=panorama, username=username, password=password)
        await pan.login()
        await set_device_groups(pan=pan)
        if deep:
            my_objs = await get_objects_panorama(pan, names_only=False)
        else:
            my_objs = await get_objects_panorama(pan)

    print("\n\tDe-duplicating...\n")
    results = {}
    for object_type in settings.to_dedupe:
        results[object_type] = {}
        if deep:
            duplicates = find_duplicates_deep(my_objs[object_type])
        else:
            duplicates = find_duplicates(my_objs[object_type])

        # Only duplicates that meet 'minimum' count
        for dupe, dgs in duplicates.items():
            if len(dgs) >= settings.minimum_duplicates:
                results[object_type].update({dupe: dgs})

    write_output(results)
    print("\nDuplicates found: \n")

    length = 0
    length += sum([len(v) for k, v in results.items()])
    if length == 0:
        print("\nNone!")
    else:
        pprint(results)
        pprint(f"{length} objects found in total.")

        if settings.push_to_panorama and not configstr:
            yesno = ""
            while yesno not in ("y", "n", "yes", "no"):
                yesno = input(
                    "About to begin moving duplicate objects...continue? (y/n): "
                )
            if yesno in ("yes", "y"):
                await push_to_panorama(pan=pan, results=results)

    print("\n\tDone! Output above also saved in duplicates.json.\n")
    logger.info("Done.")


async def push_to_panorama(pan, results) -> None:
    """
    Push the changes to Panorama

    Delete objects from local device groups
    Add objects to parent device group

    Args:
        pan: panorama api object
        results: duplicates to be cleaned up
    Returns:
         N/A
    Raises:
        N/A
    """
    print("\nBeginning push..")
    print("Getting full objects...\n")
    # Get full objects so we can create them elsewhere
    my_objs = await get_objects_panorama(pan=pan, names_only=False)

    # Order of creation/deletion is super important...thus hard-coded here
    # Do the creates
    print(
        "\n\n`tail -f` or open 'deduper.log' in your favorite editor to watch the show..\n"
    )
    print("\nCreating objects...")
    await do_the_creates(
        object_types=["addresses", "services"],
        pan=pan,
        results=results,
        objs_list=my_objs,
    )
    print("\nCreating object groups...")
    await do_the_creates(
        object_types=["address-groups", "service-groups"],
        pan=pan,
        results=results,
        objs_list=my_objs,
    )

    # Now do the deletes
    print("\nDeleting object groups...")
    await do_the_deletes(
        object_types=["address-groups", "service-groups"], pan=pan, results=results
    )
    print("\nDeleting objects...")
    await do_the_deletes(
        object_types=["addresses", "services"], pan=pan, results=results
    )

    # Now lets delete shared (to delete!!)
    if settings.delete_shared_objects:
        yesno = ""
        while yesno not in ("y", "n", "yes", "no"):
            yesno = input("All cleaned up...cleanup 'shared' also? (y/n): ")
        if yesno in ("yes", "y"):
            shared_objs = await get_objects_panorama(
                pan=pan, shared=True, names_only=True
            )

            # Find shared dupes
            shared_deletes = find_duplicates_shared(
                shared_objs=shared_objs, dupes=results
            )

            print("Deleting from 'shared'...")
            await do_the_deletes_shared(
                object_types=["address-groups", "service-groups"],
                pan=pan,
                objects=shared_deletes,
            )
            await do_the_deletes_shared(
                object_types=["addresses", "services"], pan=pan, objects=shared_deletes
            )

    return None


async def set_device_groups(*, config=None, pan: Panorama_api = None):
    """
    Set the device groups that will be searched through

    Args:
        only 1 of below should be provided
        config: xml config string (if provided)
        pan: panorama object (if provided)
    Returns:
        N/A
    Raises:
         N/A
    """
    if config is not None:
        if not settings.device_groups:
            dgs = config.find(
                "devices/entry[@name='localhost.localdomain']/device-group"
            )
            for entry in dgs.getchildren():
                settings.device_groups.append(entry.get("name"))
    else:
        if not settings.device_groups:
            settings.device_groups = await pan.get_device_groups()

    if settings.exclude_device_groups:
        for dg in settings.exclude_device_groups:
            if dg in settings.device_groups:
                settings.device_groups.remove(dg)

    print(f"\nComparing these DEVICE GROUPS:\n{settings.device_groups}")
    print(f"\nand these OBJECT TYPES:\n{settings.to_dedupe}\n")


async def get_objects_panorama(
    pan: Panorama_api, names_only: bool = True, shared: bool = False
):
    """
    Get objects from Panorama API

    Args:
        pan:    Panorama API Object
        names_only: return only the names or the full object
        shared: pull from shared (to delete!)
    Returns:
         Dict/List of objects
    Raises:
        N/A
    """

    # Get objects
    coroutines = [
        _get_objects_panorama(pan, object_type, names_only, shared)
        for object_type in settings.to_dedupe
    ]
    my_objs_temp = await asyncio.gather(*coroutines)

    # Convert/merge list of dicts into one dictionary
    my_objs = {}
    for obj in my_objs_temp:
        my_objs.update(obj)
    return my_objs


async def _get_objects_panorama(
    pan: Panorama_api, object_type: str, names_only: bool = True, shared: bool = False
):
    my_objs = {object_type: {}}

    print(f"Getting {object_type}/checking for duplicates..")

    if shared:
        params = {"location": "shared"}
        objs = await pan.get_objects(object_type=object_type, params=params)
        if not objs:
            print(f"No {object_type} found in 'shared', moving on...")
            my_objs[object_type]["shared"] = set([])
        else:
            my_objs[object_type]["shared"] = format_objs(
                objs=objs, dg="shared", names_only=names_only
            )
    else:
        for dg in settings.device_groups:
            my_objs[object_type][dg] = []
            # Get objects
            params = {"location": "device-group", "device-group": f"{dg}"}
            objs = await pan.get_objects(object_type=object_type, params=params)
            if not objs:
                print(f"No {object_type} found in {dg}, moving on...")
                my_objs[object_type][dg] = set([])
            else:
                my_objs[object_type][dg] = format_objs(
                    objs=objs, dg=dg, names_only=names_only
                )

    return my_objs


def format_objs(objs, dg, names_only):
    formatted_objs = []

    if not names_only:
        formatted_objs = objs
    else:
        for name in objs:
            obj_name = None
            if dg == "shared":
                obj_name = name["@name"]
            else:
                if name["@loc"] not in settings.parent_device_group:
                    obj_name = name["@name"]
            formatted_objs.append(obj_name)

        formatted_objs = set(formatted_objs)

    return formatted_objs


async def get_objects_xml(configstr, deep = None):
    """
    Get objects from xml file instead of Panorama

    Args:
        configstr: xml filename
    Returns:
         Dict/list of objects
    Raises:
        N/A
    """
    try:
        config = etree.fromstring(configstr)
    except XMLSyntaxError as exc:
        print(exc)
        print("\nInvalid XML File...try again! Our best guess is up there ^^^\n")
        sys.exit(1)

    # Get device groups and compare/merge with settings.py
    await set_device_groups(config=config)

    # Get objects - build into x[type][device-group][name1,name2,...]
    my_objs = {}
    for object_type in settings.to_dedupe:
        my_objs[object_type] = {}
        for dg in settings.device_groups:
            object_xpath = None
            if object_type == "addresses":
                object_xpath = f"//devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/address/entry"
            if object_type == "address-groups":
                object_xpath = f"//devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/address-group/entry"
            if object_type == "services":
                object_xpath = f"//devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/service/entry"
            if object_type == "service-groups":
                object_xpath = f"//devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/service-group/entry"

            # Get object
            objs = config.xpath(object_xpath)

            if not objs:
                print(f"No {object_type} found in {dg}, moving on...")
                my_objs[object_type][dg] = set([])
                continue

            if deep:
                my_objs[object_type][dg] = set(objs)
            else:
                my_objs[object_type][dg] = set([name.get("name") for name in objs])

    return my_objs


def find_duplicates(my_objects):
    """
    Finds the duplicate objects (multiple device groups contain the object)

    Args:
     my_objects: list of objects to search through
    Returns:
        duplicates: Dict of duplicate object names containing list of device-groups]
    Raises:
        N/A
    """
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


def find_duplicates_deep(my_objects):
    """
    Finds the duplicate objects (multiple device groups contain the object)

    Args:
     my_objects: list of objects to search through
    Returns:
        duplicates: Dict of duplicate object names containing list of device-groups]
    Raises:
        N/A
    """
    duplicates = {}
    for items in combinations(my_objects, r=2):
        for obj in my_objects[items[0]]:
            for obj2 in my_objects[items[1]]:
                if obj["@name"] == obj2["@name"]:
                    for key in ("@device-group", "@loc", "@location"):
                        if obj.get(key):
                            obj.pop(key)
                        if obj2.get(key):
                            obj2.pop(key)

                    if obj == obj2:
                        if duplicates.get(obj["@name"]):
                            if items[0] not in duplicates[obj["@name"]]:
                                duplicates[obj["@name"]].append(items[0])
                            if items[1] not in duplicates[obj["@name"]]:
                                duplicates[obj["@name"]].append(items[1])
                        else:
                            duplicates[obj["@name"]] = list(items)
                    else:
                        print("Deep check found same name but different values:")
                        print(f"\n{obj['@name']}\n")
                        pprint(obj)
                        print("\n\n")
                        print(f"\n{obj2['@name']}\n")
                        pprint(obj2)
                        print("\n\n")

    return duplicates


def find_duplicates_shared(shared_objs, dupes):

    shared_duplicates = {}
    for object_type in dupes:
        shared_duplicates[object_type] = []
        for obj_name in dupes[object_type]:
            # print(f"{obj_name=}\t {shared_objs[object_type]['shared']}")
            if obj_name in shared_objs[object_type]["shared"]:
                print(f"found dupe in shared: {obj_name}")
                shared_duplicates[object_type].append(obj_name)

    return shared_duplicates


def find_object(objs_list, object_type, device_group, name):
    """
    Find object to be used for creation in parent device group

    Args:
        objs_list:  List of objects to search through
        object_type:    address/group/services/groups
        device_group:  device group
        name:   name of object to find
    Returns:
         The object you were looking for
    Raises:
        N/A
    """

    for obj in objs_list[object_type][device_group]:
        if obj.get("@name"):
            if obj["@name"] == name:
                return obj

    return None


async def do_the_creates(
    pan: Panorama_api, results: Dict, object_types: List[str], objs_list: Any
):
    coroutines = []
    for object_type in object_types:
        if results.get(object_type):
            for dupe, device_groups in results[object_type].items():

                # Get full object
                dupe_obj = find_object(
                    objs_list=objs_list,
                    object_type=object_type,
                    device_group=device_groups[0],  # just grab the object from the 1st dg
                    name=dupe,
                )

                # Create it
                coroutines.append(
                    pan.create_object(
                        object_type=object_type,
                        obj=dupe_obj,
                        device_group=settings.parent_device_group,
                    )
                )

    await asyncio.gather(*coroutines)


async def do_the_deletes(pan: Panorama_api, results: Dict, object_types: List[str]):
    coroutines = []
    for object_type in object_types:
        if results.get(object_type):
            for dupe, device_groups in results[object_type].items():
                for dg in device_groups:
                    coroutines.append(
                        pan.delete_object(
                            object_type=object_type, name=dupe, device_group=dg
                        )
                    )

    await asyncio.gather(*coroutines)


async def do_the_deletes_shared(
    pan: Panorama_api, objects: Dict, object_types: List[str]
):
    coroutines = []
    params = {"location": "shared"}
    for object_type in object_types:
        if objects.get(object_type):
            for dupe in objects[object_type]:
                coroutines.append(
                    pan.delete_object(object_type=object_type, name=dupe, params=params)
                )

    await asyncio.gather(*coroutines)


def write_output(results):
    """
    Write json string to file

    Args:
        results: dictionary of duplicate results
    Returns:
         N/A
    Raises:
        N/A
    """
    # Write output to file
    json_str = json.dumps(results, indent=4)

    dt = datetime.now().strftime("%Y-%m-%d::%H:%M:%S")
    with open(f"duplicates-{dt}.json", "w") as fout:
        fout.write(json_str)
