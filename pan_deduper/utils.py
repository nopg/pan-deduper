"""pan_deduper.utils"""
import asyncio
import importlib.resources as pkg_resources
import importlib.util
import inspect
import json
import logging
import sys
from datetime import datetime
from itertools import combinations
from typing import Any, Dict, List, Set, Union

import xmltodict
from deepdiff import DeepDiff
from lxml import etree
from lxml.etree import XMLSyntaxError, XPathEvalError
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
        with open("settings.py", "w", encoding="utf8") as f:
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
    deep: bool = False,
) -> None:
    """
    Main program - BEGIN!

    Args:
        configstr:  xml config file string
        panorama:   panorama IP/FQDN
        username:   panorama username
        password:   panorama password
    """
    logger.info("")
    logger.info("----Running deduper---")
    logger.info("")

    my_objs = []

    if configstr:
        my_objs = await get_objects_xml(configstr, deep)

    elif panorama:
        pan = Panorama_api(panorama=panorama, username=username, password=password)
        await pan.login()
        # settings.EXISTING_PARENT_DGS = await pan.get_parent_dgs()
        # print("Parent Device Groups:")
        # pprint(settings.EXISTING_PARENT_DGS)
        await set_device_groups(pan=pan, deep=deep)
        if deep:
            my_objs = await get_objects_panorama(pan, names_only=False)
        else:
            my_objs = await get_objects_panorama(pan)

    print("\n\tDe-duplicating...\n")
    if settings.MINIMUM_DUPLICATES <= 0:
        print("Minimum duplicates set to 0, what are you doing?")
        sys.exit()
    results = {}
    deep_dupes = {}
    for object_type in settings.TO_DEDUPE:
        objs = my_objs[object_type]
        results[object_type] = {}

        if deep:
            duplicates, deep_dupes[object_type] = find_duplicates_deep(
                my_objects=objs, xml=configstr
            )
        else:
            duplicates = find_duplicates(my_objects=objs)

        # Only duplicates that meet 'minimum' count
        for dupe, dgs in duplicates.items():
            if dupe:
                if len(dgs) >= settings.MINIMUM_DUPLICATES:
                    results[object_type].update({dupe: dgs})

    if deep:
        write_output("deep-dupes", deep_dupes)
        print(
            "\n\tAlmost/Maybe duplicates found with deep check are saved in deep-dupes.json"
        )

    write_output("duplicates", results)
    print("\nDuplicates found: \n")

    length = 0
    length += sum([len(v) for k, v in results.items()])
    changes = 0
    for _, obj_type in results.items():
        for _, device_groups in obj_type.items():
            changes += len(device_groups)

    if length == 0:
        print("\nNone!")
    else:
        pprint(f"{length} objects found in total.")
        pprint(f"{changes} object changes.")
        if changes <= 50:
            pprint(results)
        else:
            answer = ask_user("Print them all? (y/n)")
            if answer in ("yes", "y"):
                pprint(results)
        if settings.PUSH_TO_PANORAMA and not configstr:
            answer = ask_user("About to begin moving duplicate objects...continue? (y/n): ")
            if answer in ("yes", "y"):
                await push_to_panorama(pan=pan, results=results)

    print("\n\tDone! Results(duplicate list) also saved in duplicates.json.\n")
    logger.info("Done.")


def get_any_tags(objs):
    """
    Get any tags so that we can build the objects properly

    Args:
        objs: dict of duplicate objects {type: {dg: [objs]} }

    Returns:
        tags: Dict of tags {dg: [tag names]}
    """
    tags = {}

    # Create Dict of {DG: [Tag names]}
    for object_type, device_groups in objs.items():
        for group, objects in device_groups.items():
            for obj in objects:
                if obj.get("tag"):
                    members = obj["tag"].get("member")
                    if members:
                        for tag in obj["tag"]["member"]:
                            # Create empty if this is the first
                            if not tags.get(group):
                                tags[group] = []
                            # Add Tag to list
                            if tag not in tags[group]:
                                tags[group].append(tag)
                    else:
                        message = f"Error pulling tag from: {obj}, exiting.."
                        logger.error(message)
                        print(message)
                        sys.exit(1)

    return tags


async def create_tags(tags, pan: Panorama_api):
    """
    Create the tags

    Args:
        tags: Dict of tags {dg: [tag names]}
        pan: Panorama API Object
    """

    # Reorganize and ignore any duplicate names
    # 1st tag found will be used as the clone in parent device group
    to_create = {}
    tag_list = []
    for dg, tags in tags.items():
        for tag in tags:
            if tag not in tag_list:
                tag_list.append(tag)
                if not to_create.get(dg):
                    to_create[dg] = []
                to_create[dg].append(tag)

    # Get and create tags
    coroutines = []
    for dg, tags in to_create.items():
        for tag in tags:
            params = {"location": "device-group", "device-group": f"{dg}", "name": tag}
            full_tag = await pan.get_objects(
                object_type="tags", device_group=dg, params=params
            )
            if not full_tag:
                error = f"Error pulling tag {tag} from {dg}, must be inherited, skipping"
                print(error)
                logger.error(error)
                continue
            full_tag = full_tag[0]
            coroutines.append(
                pan.create_object(
                    object_type="tags",
                    obj=full_tag,
                    device_group=settings.NEW_PARENT_DEVICE_GROUP,
                )
            )

    await asyncio.gather(*coroutines)


async def delete_tags(tags, pan: Panorama_api):
    """
    Delete the tags
    Args:
        tags: Dict of tags {dg: [tag names]}
        pan: Panorama API Object
    """
    coroutines = []
    for dg, tags in tags.items():
        for tag in tags:
            coroutines.append(
                pan.delete_object(object_type="tags", name=tag, device_group=dg)
            )

    await asyncio.gather(*coroutines)


async def cleanup_tags(tags, pan: Panorama_api):
    """
    Can't create the objects in Parent-DG if the Tag doesn't also exist there

    Args:
        tags: Dict of tags {dg: [tag names]}
        pan: Panorama API Object
    """
    await create_tags(tags=tags, pan=pan)
    await delete_tags(tags=tags, pan=pan)


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
    if not settings.NEW_PARENT_DEVICE_GROUP:
        print("\n\nYou didn't give me a parent device group to add objects to!!")
        print("Check settings.py\n\n")
        sys.exit(1)

    print("\nBeginning push..")
    print("Getting full objects...\n")
    # Get full objects so we can create them elsewhere
    my_objs = await get_objects_panorama(pan=pan, names_only=False)

    print("\nChecking for any tags to clean up as well...")
    my_tags = get_any_tags(objs=my_objs)
    await cleanup_tags(tags=my_tags, pan=pan)

    # Order of creation/deletion is super important...thus hard-coded here
    # Do the creates
    print(
        "\n\nThis may take awhile, the Panorama management plane is frustratingly slow as we all know...please wait!"
    )
    print(
        "\n`tail -f` or open 'deduper.log' in your favorite editor to watch the show..\n"
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
    if settings.DELETE_SHARED_OBJECTS:
        answer = ask_user("\n\tAll cleaned up...cleanup 'shared' also? (y/n): ")
        if answer in ("yes", "y"):
            shared_objs = await get_objects_panorama(
                pan=pan, shared=True, names_only=True
            )

            # Find shared dupes
            shared_deletes = find_duplicates_shared(
                shared_objs=shared_objs, dupes=results
            )

            if not shared_deletes:
                print("\tNothing to delete")
            else:
                print("Deleting from 'shared'...")
                await do_the_deletes_shared(
                    object_types=["address-groups", "service-groups"],
                    pan=pan,
                    objects=shared_deletes,
                )
                await do_the_deletes_shared(
                    object_types=["addresses", "services"],
                    pan=pan,
                    objects=shared_deletes,
                )

    return None


async def set_device_groups(*, config=None, pan: Panorama_api = None, deep: bool):
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
        if not settings.DEVICE_GROUPS:
            dgs = config.find(
                "devices/entry[@name='localhost.localdomain']/device-group"
            )
            if dgs is not None:
                for entry in dgs.getchildren():
                    settings.DEVICE_GROUPS.append(entry.get("name"))
    else:
        if not settings.DEVICE_GROUPS:
            settings.DEVICE_GROUPS = await pan.get_device_groups()

    if settings.EXCLUDE_DEVICE_GROUPS:
        for dg in settings.EXCLUDE_DEVICE_GROUPS:
            if dg in settings.DEVICE_GROUPS:
                settings.DEVICE_GROUPS.remove(dg)

    settings_message = f"""
    ------------------------
    Settings for this run:
    
    OBJECT TYPES: \t{', '.join(obj_type for obj_type in settings.TO_DEDUPE)}
    DEVICE GROUPS: \t{', '.join(dg for dg in settings.DEVICE_GROUPS)}
    CLEANUP PARENTS: \t{', '.join(dg for dg in settings.CLEANUP_DGS)}
    MINIMUM DUPLICATES: \t{settings.MINIMUM_DUPLICATES}
    DEEP DEDUPE: \t\t{deep}
    PUSH TO PANORAMA: \t\t{settings.PUSH_TO_PANORAMA}
    DELETE SHARED OBJECTS: \t{settings.DELETE_SHARED_OBJECTS}
    NEW PARENT DEVICE GROUP: \t{', '.join(dg for dg in settings.NEW_PARENT_DEVICE_GROUP)}
    ------------------------
    
    """
    logger.info(settings_message)
    print(inspect.cleandoc(settings_message))

    answer = ask_user("DO THE ABOVE SETTINGS LOOK CORRECT? Ensure Panorama candidate config state is as desired as well! (y/n): ")

    if answer in ("no", "n"):
        print("Exiting..")
        sys.exit()
    print("\n\n")


def ask_user(question: str):
    answer = ""
    while answer.lower() not in ("y", "n", "yes", "no"):
        answer = input(
            "DO THE ABOVE SETTINGS LOOK CORRECT? Ensure Panorama candidate config state is as desired as well! (y/n): "
        )
    return answer.lower()


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
    """

    # Get objects
    coroutines = [
        _get_objects_panorama(pan, object_type, names_only, shared)
        for object_type in settings.TO_DEDUPE
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
                objs=objs, device_group="shared", names_only=names_only
            )
    else:
        for dg in settings.DEVICE_GROUPS:
            my_objs[object_type][dg] = []
            # Get objects
            params = {"location": "device-group", "device-group": f"{dg}"}
            objs = await pan.get_objects(object_type=object_type, params=params)
            if not objs:
                print(f"No {object_type} found in {dg}, moving on...")
                my_objs[object_type][dg] = set([])
            else:
                my_objs[object_type][dg] = format_objs(
                    objs=objs, device_group=dg, names_only=names_only
                )

    return my_objs


def format_objs(
    objs: List[Dict], device_group: str, names_only: bool
) -> Union[Set, List]:
    """
    Format objects before passing on

    Args:
        objs: objects
        device_group: device group
        names_only: return values too or just the names

    Returns:
        Set of formatted objects
    """
    formatted_objs = []

    for obj in objs:
        obj_formatted = None
        if device_group == "shared":
            obj_formatted = obj.get("@name")
        elif obj.get("@loc") in (
            device_group,
            settings.CLEANUP_DGS,
        ):  # != obj.get("location")
            if names_only:
                obj_formatted = obj["@name"]
            else:
                obj_formatted = obj
        if obj_formatted:  # If not, don't append it
            formatted_objs.append(obj_formatted)

    if names_only:
        formatted_objs = set(formatted_objs)

    return formatted_objs


async def get_objects_xml(configstr, deep=None) -> Dict:
    """
    Get objects from xml file instead of Panorama

    Args:
        configstr: xml filename
        deep: deep search or not
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

    try:
        config.xpath("./devices/entry[@name='localhost.localdomain']/device-group")
    except XPathEvalError as exc:
        print(exc)
        print(dir(exc))
        print("\nInvalid XML File...try again! Our best guess is up there ^^^\n")
        sys.exit(1)

    # Get device groups and compare/merge with settings.py
    await set_device_groups(config=config, deep=deep)

    # Get objects - build into x[type][device-group][name1,name2,...]
    my_objs = {}
    for object_type in settings.TO_DEDUPE:
        my_objs[object_type] = {}
        for dg in settings.DEVICE_GROUPS:
            object_xpath = None
            if object_type == "addresses":
                object_xpath = f"./devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/address/entry"
            if object_type == "address-groups":
                object_xpath = f"./devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/address-group/entry"
            if object_type == "services":
                object_xpath = f"./devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/service/entry"
            if object_type == "service-groups":
                object_xpath = f"./devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/service-group/entry"

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
        dg1 = items[0]
        dg2 = items[1]

        dupes = my_objects[dg1].intersection(my_objects[dg2])

        for obj in dupes:
            if duplicates.get(obj):
                if dg1 not in duplicates[obj]:
                    duplicates[obj].append(dg1)
                if dg2 not in duplicates[obj]:
                    duplicates[obj].append(dg2)
            else:
                duplicates[obj] = list(items)

    return duplicates


def find_duplicates_deep(my_objects, xml: Union[None, str]):
    """
    Finds the duplicate objects (multiple device groups contain the object)

    Args:
        my_objects: list of objects to search through
        xml: are we parsing xml or not?
    Returns:
        duplicates: Dict of duplicate object names containing list of device-groups]
    Raises:
        N/A
    """
    duplicates = {}
    diffs = []
    nametag = "name" if xml else "@name"
    for items in combinations(my_objects, r=2):
        dg1 = items[0]
        dg2 = items[1]
        for obj1 in my_objects[dg1]:
            for obj2 in my_objects[dg2]:
                # We are now comparing two lists of objects
                if obj1 is not None and obj2 is not None:
                    if obj1.get(nametag) == obj2.get(nametag):
                        dupe_name = obj1.get(nametag)
                        if xml:  # Convert to Dict so we can use Deep Diff
                            dupe_obj1 = xmltodict.parse(etree.tostring(obj1))["entry"]
                            dupe_obj2 = xmltodict.parse(etree.tostring(obj2))["entry"]
                        else:
                            dupe_obj1 = obj1
                            dupe_obj2 = obj2

                        # Don't need these keys, will cause dupe checking issues too
                        for key in ("@loc", "@location", "@device-group", "@overrides"):
                            if dupe_obj1.get(key):
                                dupe_obj1.pop(key)
                            if dupe_obj2.get(key):
                                dupe_obj2.pop(key)

                        # Deep Diff!
                        diff = DeepDiff(dupe_obj1, dupe_obj2, ignore_order=True)
                        if not diff:
                            # We have a dupe! Add the dupe & device-groups to our list
                            if dupe_name is None:
                                print("how did this happen??")
                            else:
                                if duplicates.get(dupe_name):
                                    if dg1 not in duplicates[dupe_name]:
                                        duplicates[dupe_name].append(dg1)
                                    if dg2 not in duplicates[dupe_name]:
                                        duplicates[dupe_name].append(dg2)
                                else:
                                    duplicates[dupe_name] = list(items)
                        else:
                            # weirdness required due to json.dumps("@blah"), to be betterized
                            temp1 = {"@device-group": dg1}
                            temp2 = {"@device-group": dg2}
                            temp1.update(dupe_obj1)
                            temp2.update(dupe_obj2)
                            diffs.append([temp1, temp2])
                            print(
                                f"Deep check found {temp1.get('@name')} in {temp1.get('@device-group')} and {temp2.get('@name')} in {temp2.get('@device-group')}"
                            )
    return duplicates, diffs


def find_duplicates_shared(shared_objs, dupes) -> Dict[str, List]:
    """
    Find duplicates for shared (it's always separate!)

    Args:
        shared_objs: shared objects
        dupes: pre-determined duplicates

    Returns:
        Dictionary of the duplicates sorted by object type
    """

    shared_duplicates = {}
    for object_type in dupes:
        shared_duplicates[object_type] = []
        for obj_name in dupes[object_type]:
            # print(f"{obj_name=}\t {shared_objs[object_type]['shared']}")
            if obj_name in shared_objs[object_type]["shared"]:
                print(f"\n\tFound duplicate in shared: {obj_name}")
                shared_duplicates[object_type].append(obj_name)

    return shared_duplicates


def find_object(objs_list, object_type, device_group, name):
    """
    Find object to be used for creation in parent device group

    Args:
        objs_list:  Dict of objects to search through
        object_type:    address/group/services/groups
        device_group:  device group
        name:   name of object to find
    Returns:
         The object you were looking for
    Raises:
        N/A
    """

    for obj in objs_list[object_type][device_group]:
        if obj:
            try:
                if obj.get("@name") == name:
                    return obj
            except AttributeError:
                message = f"""
                    Error searching through objects list, exiting due to major malfunction.
                    obj == {obj}
                """
                logger.error(message)
                print(message)
                sys.exit(1)

    return None


async def do_the_creates(
    pan: Panorama_api, results: Dict, object_types: List[str], objs_list: Any
) -> None:
    """
    Create the objects

    Args:
        pan: panorama_api object
        results: objects (duplicates) to be created (as part of 'move')
        object_types: object types to be created (used to create objects before groups)
        objs_list: full object values so that we can clone them

    """
    coroutines = []
    for object_type in object_types:
        if results.get(object_type):
            for dupe, device_groups in results[object_type].items():

                # Get full object
                dupe_obj = find_object(
                    objs_list=objs_list,
                    object_type=object_type,
                    device_group=device_groups[
                        0
                    ],  # just grab the object from the 1st dg
                    name=dupe,
                )

                # Create it
                coroutines.append(
                    pan.create_object(
                        object_type=object_type,
                        obj=dupe_obj,
                        device_group=settings.NEW_PARENT_DEVICE_GROUP,
                    )
                )

    await asyncio.gather(*coroutines)


async def do_the_deletes(
    pan: Panorama_api, results: Dict, object_types: List[str]
) -> None:
    """
    Delete the objects

    Args:
        pan: panorama_api object
        results: objects (duplicates) to be deleted
        object_types: object types to be deleted (used to send groups in before objects)

    """
    coroutines = []
    for object_type in object_types:
        if results.get(object_type):
            for dupe, device_groups in results[object_type].items():
                for group in device_groups:
                    if group in settings.NEW_PARENT_DEVICE_GROUP:  # do this better?
                        continue
                    coroutines.append(
                        pan.delete_object(
                            object_type=object_type, name=dupe, device_group=group
                        )
                    )

    await asyncio.gather(*coroutines)


async def do_the_deletes_shared(
    pan: Panorama_api, objects: Dict, object_types: List[str]
) -> None:
    """
    Delete the shared objects

    Args:
        pan: panorama_api object
        objects: objects (duplicates) to be deleted
        object_types: object types to be deleted (used to send groups in before objects)
    """
    coroutines = []
    params = {"location": "shared"}
    for object_type in object_types:
        if objects.get(object_type):
            for dupe in objects[object_type]:
                coroutines.append(
                    pan.delete_object(object_type=object_type, name=dupe, params=params)
                )

    await asyncio.gather(*coroutines)


def write_output(filename, output):
    """
    Write json string to file

    Args:
        filename: you get one guess
        output: dictionary to be saved
    """

    class SetEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, set):
                return list(obj)
            return json.JSONEncoder.default(self, obj)

    # Write output to file
    json_str = json.dumps(output, indent=4, cls=SetEncoder, sort_keys=True)
    dt = datetime.now().strftime("%Y-%m-%d::%H:%M:%S")
    with open(f"{filename}-{dt}.json", "w", encoding="utf8") as f:
        f.write(json_str)
