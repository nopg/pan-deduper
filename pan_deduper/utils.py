"""pan_deduper.utils"""
import asyncio
import importlib.resources as pkg_resources
import importlib.util
import inspect
import json
import logging
import re
import sys
from datetime import datetime
from itertools import combinations
from typing import Any, Dict, List, Set, Tuple, Union

import xmltodict
from deepdiff import DeepDiff
from lxml import etree
from lxml.etree import XMLSyntaxError, XPathEvalError
from rich.pretty import pprint

from pan_deduper.panorama_api import PanoramaApi

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


# def sec_rules_xml(configstr: str):
#     rules = get_sec_rules_xml(configstr, "pre")
#     t = rules[0]
#     #print(dir(rules[0]))
#     #breakpoint()
#     #print(t.items)
#     for child in t.getchildren():
#         print(child.tag)
#         member = child.find('member')
#         breakpoint()
#         if member is not None:
#             print(member.text)
#         else:
#             print(child.text)


async def get_sec_rules(pan: PanoramaApi, device_group: str):
    rules = {device_group: {}}
    rules[device_group]["pre"] = await pan.get_objects(object_type="secrules-pre", device_group=device_group)
    rules[device_group]["post"] = await pan.get_objects(object_type="secrules-post", device_group=device_group)

    return rules


def check_sec_rules(rules: Dict):
    rule_updates = {}
    for i1, rule1 in enumerate(rules):
        if rule1['@loc'] != rule1['@device-group']:
            continue
        for i2, rule2 in enumerate(rules[i1:]):  # Only check rules BELOW my current rule
            name1 = rule1["@name"]
            name2 = rule2["@name"]
            action1 = rule1['action']
            action2 = rule2['action']
            src_zone1 = set(rule1['from']['member'])
            src_zone2 = set(rule2['from']['member'])
            destination1 = set(rule1['destination']['member'])
            destination2 = set(rule2['destination']['member'])
            service1 = set(rule1['service']['member'])
            service2 = set(rule2['service']['member'])
            application1 = set(rule1['application']['member'])
            application2 = set(rule2['application']['member'])

            # Continue if same rule, break if I hit a deny and start on next rule
            if name1 == name2:
                continue
            if action2 == "deny" and action1 != "deny":
                break
            if rule2['@loc'] != rule2['@device-group']:  # If it was inherited
                continue

            if action1 == action2:
                if destination2 == destination1:
                    if service1 == service2:
                        if application1 == application2:
                            if src_zone2 == src_zone1:
                                if not rule_updates.get(rule1['@name']):
                                    rule_updates[rule1['@name']] = [rule2]
                                else:
                                    rule_updates[rule1['@name']].append(rule2)

    return rule_updates


def create_set_rule_output(updates, rulebase):
    output = []
    deleted_rules = []
    if rulebase == "pre":
        prepost = "pre-rulebase"
    else:
        prepost = "post-rulebase"
    for rule, additions in updates.items():
        if rule in deleted_rules:
            continue
        for add in additions:
            sets = []
            deletes = []
            source = add['source']['member']
            for item in source:
                if item == 'any':
                    delete_cmd = (
                        f"delete device-group {add['@device-group']} {prepost} security rules '{rule}' source"
                    )
                    deletes.append(delete_cmd)
                set_cmd = (
                    f"set device-group {add['@device-group']} {prepost} security rules '{rule}' source {item}"
                )
                sets.append(set_cmd)

            # Now delete the old rule
            delete_cmd = (
                f"delete device-group {add['@device-group']} {prepost} security rules '{add['@name']}'"
            )
            deletes.append(delete_cmd)
            deleted_rules.append(add['@name'])

            output += sets + deletes
        output.append('\n')

    return output


async def run_secduper(
    panorama: str = None,
    username: str = None,
    password: str = None,
) -> None:

    pan = PanoramaApi(panorama=panorama, username=username, password=password)
    await pan.login()

    my_rules = {}
    if not settings.DEVICE_GROUPS:
        settings.DEVICE_GROUPS = await pan.get_device_groups()
    coroutines = []
    for group in settings.DEVICE_GROUPS:
        coroutines.append(get_sec_rules(pan=pan, device_group=group))

    my_rules_temp = await asyncio.gather(*coroutines)
    my_rules = {}
    for group in my_rules_temp:
        my_rules.update(group)

    cmds = {}
    for device_group, rules in my_rules.items():
        cmds[device_group] = {}
        print(f"checking {device_group} Pre")
        updates = check_sec_rules(rules["pre"])
        cmds[device_group]["pre"] = [f"--------- PRE-RULEBASE ---------"]
        cmds[device_group]["pre"] += create_set_rule_output(updates, "pre")

        print(f"checking {device_group} Post")
        updates = check_sec_rules(rules["post"])
        cmds[device_group]["post"] = [f"--------- POST-RULEBASE ---------"]
        cmds[device_group]["post"] += create_set_rule_output(updates, "post")

    #pprint(cmds)

    for device_group, rulebases in cmds.items():
        with open(f"set-commands-sec_rules-{device_group}.txt", "w") as fin:
            for prepost in rulebases:
                if prepost:
                    for cmd in cmds[device_group][prepost]:
                        fin.write(f"{cmd}\n")

    print("Done! Output of each device group at: set-commands-sec_rules-<groupname>.txt")


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
        deep:       deep check or not
    """
    logger.info("")
    logger.info("----Running deduper---")
    logger.info("")

    my_objs = []

    if configstr:
        my_objs = await get_objects_xml(configstr, deep)

    elif panorama:
        pan = PanoramaApi(panorama=panorama, username=username, password=password)
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
            else:
                print()
        if settings.PUSH_TO_PANORAMA and not configstr:
            answer = ask_user(
                "About to begin moving duplicate objects...continue? (y/n): "
            )
            if answer in ("yes", "y"):
                await object_creation_deletion(pan=pan, results=results)
        elif settings.SET_OUTPUT:
            answer = ask_user("Ready to create set commands...continue? (y/n): ")
            if answer in ("yes", "y"):
                if 'pan' not in locals():
                    print("Not currently supported via XML.")
                    sys.exit()
                await create_set_output(pan=pan, results=results)

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


async def create_tags(tags, pan: PanoramaApi, set_output: bool):
    """
    Create the tags

    Args:
        tags: Dict of tags {dg: [tag names]}
        pan: Panorama API Object
        set_output: set commands or no?
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
    limit = asyncio.Semaphore(value=settings.MAX_CONCURRENT)
    for dg, tags in to_create.items():
        for tag in tags:
            params = {"location": "device-group", "device-group": f"{dg}", "name": tag}
            full_tag = await pan.get_objects(
                object_type="tags", device_group=dg, params=params
            )
            if not full_tag:
                # # Check shared
                # params = {"location": "shared", "name": tag}
                # full_tag = await pan.get_objects(
                #     object_type="tags",  params=params
                # )
                # if full_tag:
                #     print(f"found {full_tag=} in shared")
                #     full_tag[0]["@name"] = "FOUND_IN_SHARED-" + full_tag[0]["@name"]
                #     print(f"found {full_tag=} in shared")
                # else:
                error = f"Error pulling tag {tag} from {dg}, must be complex hierarchy, please fix manually."
                print(error)
                logger.error(error)
                continue
            full_tag = full_tag[0]
            coroutines.append(
                pan.create_object(
                    limit=limit,
                    object_type="tags",
                    obj=full_tag,
                    device_group=settings.NEW_PARENT_DEVICE_GROUP,
                    set_output=set_output,
                )
            )

    return await asyncio.gather(*coroutines)


async def delete_tags(tags, pan: PanoramaApi, set_output: bool):
    """
    Delete the tags
    Args:
        tags: Dict of tags {dg: [tag names]}
        pan: Panorama API Object
        set_output: set commands or no?
    """
    limit = asyncio.Semaphore(value=settings.MAX_CONCURRENT)
    coroutines = []
    for dg, tags in tags.items():
        for tag in tags:
            params = None
            if tag.startswith("FOUND_IN_SHARED-"):
                tag = tag.replace("FOUND_IN_SHARED", "")
                params = {"location": "shared"}
            coroutines.append(
                pan.delete_object(
                    limit=limit,
                    object_type="tags",
                    name=tag,
                    device_group=dg,
                    params=params,
                    set_output=set_output,
                )
            )

    return await asyncio.gather(*coroutines)


async def cleanup_tags(tags, pan: PanoramaApi, set_output: bool):
    """
    Can't create the objects in Parent-DG if the Tag doesn't also exist there

    Args:
        tags: Dict of tags {dg: [tag names]}
        pan: Panorama API Object
        set_output: set commands or no?
    """
    tag_commands = []
    tags_create = await create_tags(tags=tags, pan=pan, set_output=set_output)
    tags_delete = await delete_tags(tags=tags, pan=pan, set_output=set_output)

    if set_output:
        for tag in tags_create:
            tag_commands.append(tag)
        for tag in tags_delete:
            tag_commands.append(tag)
        return tag_commands


def reorganize_commands(commands: List, rec):
    obj_to_command = {}
    for cmd in commands:
        match = rec.search(cmd)
        if match:
            attrs = match.groupdict()
            name = attrs["obj_name"]
            if not obj_to_command.get(name):
                obj_to_command[name] = []

            obj_to_command[name].append(cmd)

    return obj_to_command


def bunch_commands(set_commands: Dict):
    re_pattern = r"""
        (?P<set_del>(set|delete))\s                                         # Set or Delete
        ((device-group\s(?P<device_group>\S+)?)                             # Device Group
        |(shared))\s                                                        # Or Shared
        (?P<obj_type>(address-group|address|service-group|service|tag))\s   # Object-type
        (\'(?P<obj_name>[^']+)\')                                           # Object Name ([^'] means anything but ')
        (?:\.+)?                                                            # Ignore anything extra
    """
    rec = re.compile(re_pattern, re.X)

    bunched_commands = {}
    for obj_type, commands in set_commands.items():
        if commands:
            obj_to_cmd = reorganize_commands(commands, rec)
            bunched_commands[obj_type] = obj_to_cmd

    return bunched_commands


async def create_set_output(pan: PanoramaApi, results) -> None:
    print("\n\nCreating set output...\n\n")
    set_commands = await object_creation_deletion(
        pan=pan, results=results, set_output=True
    )

    # Create the 'one' file
    with open("set-commands-all.txt", "w") as fin:
        for obj_type, commands in set_commands.items():
            if commands:
                for cmd in commands:
                    fin.write(f"{cmd}\n")

    print("\n\n\tSet commands at set-commands-obj-type.txt.")

    bunched_commands = bunch_commands(set_commands)

    for obj_type, obj_name in bunched_commands.items():
        with open(f"set-commands-{obj_type}.txt", "w") as fin:
            for obj, commands in bunched_commands[obj_type].items():
                if commands:
                    for cmd in commands:
                        fin.write(f"{cmd}\n")
                    fin.write("\n")


async def get_create_push_data(pan: PanoramaApi):
    if not settings.NEW_PARENT_DEVICE_GROUP:
        print("\n\nYou didn't give me a parent device group to add objects to!!")
        print("Check settings.py\n\n")
        sys.exit()

    print("Getting full objects...\n")
    # Get full objects so we can create them elsewhere
    my_objs = await get_objects_panorama(pan=pan, names_only=False)

    print("\nChecking for any tags to clean up as well...")
    my_tags = get_any_tags(objs=my_objs)

    return my_objs, my_tags


async def object_creation_deletion(
    pan: PanoramaApi, results, set_output: bool = False
) -> Union[None, Dict]:
    """
    Create and delete objects or output set commands

    Args:
        pan:
        results:
        set_output:
    Returns:

    """
    my_objs, my_tags = await get_create_push_data(pan=pan)
    set_commands = {"tags": []}

    # Cleanup tags first
    tags = await cleanup_tags(tags=my_tags, pan=pan, set_output=set_output)
    if tags:
        set_commands["tags"] += tags

    if set_output:
        for each in settings.TO_DEDUPE:
            set_commands[each] = []
            # Creates (set commands)
            cmds = await do_the_creates(
                object_types=[each],
                pan=pan,
                results=results,
                objs_list=my_objs,
                set_output=set_output,
            )
            for cmd in cmds:
                set_commands[each].append(cmd)
            # Deletes (set commands)
            cmds = await do_the_deletes(
                object_types=[each], pan=pan, results=results, set_output=set_output
            )
            # for cmd in cmds:
            #     set_commands[each].append(cmd)
            set_commands[each] += cmds

    else:  # Actually pushing to Panorama
        print("\nCreating objects...")
        await do_the_creates(
            object_types=["addresses", "services"],
            pan=pan,
            results=results,
            objs_list=my_objs,
            set_output=set_output,
        )

        print("\nCreating object groups...")
        await do_the_creates(
            object_types=["address-groups", "service-groups"],
            pan=pan,
            results=results,
            objs_list=my_objs,
            set_output=set_output,
        )

        # Now do the deletes
        print("\nDeleting object groups...")
        await do_the_deletes(
            object_types=["address-groups", "service-groups"],
            pan=pan,
            results=results,
            set_output=set_output,
        )
        print("\nDeleting objects...")
        await do_the_deletes(
            object_types=["addresses", "services"],
            pan=pan,
            results=results,
            set_output=set_output,
        )

    # Now lets delete shared (to delete!!)
    if settings.DELETE_SHARED_OBJECTS:
        if set_output:
            answer = ask_user(
                "\n\tSet commands created..create 'shared' delete commands also? (y/n): "
            )
        else:
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
                if set_output:
                    for each in settings.TO_DEDUPE + ["tags"]:
                        if set_commands.get(each):
                            # SOME duplicate must exist before looking at shared
                            if isinstance(set_commands, dict):
                                cmds = await do_the_deletes_shared(
                                    object_types=[each],
                                    pan=pan,
                                    objects=shared_deletes,
                                    set_output=set_output,
                                )
                                set_commands[each] += cmds
                else:
                    print("Deleting from 'shared'...")
                    await do_the_deletes_shared(
                        object_types=["tags"],
                        pan=pan,
                        objects=shared_deletes,
                        set_output=set_output,
                    )
                    await do_the_deletes_shared(
                        object_types=["address-groups", "service-groups"],
                        pan=pan,
                        objects=shared_deletes,
                        set_output=set_output,
                    )

                    await do_the_deletes_shared(
                        object_types=["addresses", "services"],
                        pan=pan,
                        objects=shared_deletes,
                        set_output=set_output,
                    )

    # return tags_set, creates_set, deletes_set
    if set_commands:
        return set_commands


async def set_device_groups(*, config=None, pan: PanoramaApi = None, deep: bool = None):
    """
    Set the device groups that will be searched through

    Args:
        only 1 of below should be provided
        config: xml config string (if provided)
        pan: panorama object (if provided)
        deep: deep check or not
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

    if settings.NEW_PARENT_DEVICE_GROUP:
        for parent in settings.NEW_PARENT_DEVICE_GROUP:
            settings.EXCLUDE_DEVICE_GROUPS.append(parent)

    if settings.EXCLUDE_DEVICE_GROUPS:
        for dg in settings.EXCLUDE_DEVICE_GROUPS:
            if dg in settings.DEVICE_GROUPS:
                settings.DEVICE_GROUPS.remove(dg)

    if settings.SET_OUTPUT:
        settings.PUSH_TO_PANORAMA = False

    settings_message = f"""
    ------------------------
    Settings for this run:
    
    OBJECT TYPES: \t{', '.join(obj_type for obj_type in settings.TO_DEDUPE)}
    DEVICE GROUPS: \t{', '.join(dg for dg in settings.DEVICE_GROUPS)}
    CLEANUP PARENTS: \t{', '.join(dg for dg in settings.CLEANUP_DGS)}
    MINIMUM DUPLICATES: \t{settings.MINIMUM_DUPLICATES}
    DEEP DEDUPE: \t\t{deep}
    PUSH TO PANORAMA: \t\t{settings.PUSH_TO_PANORAMA}
    SET OUTPUT: \t\t{settings.SET_OUTPUT}
    DELETE SHARED OBJECTS: \t{settings.DELETE_SHARED_OBJECTS}
    NEW PARENT DEVICE GROUP: \t{', '.join(dg for dg in settings.NEW_PARENT_DEVICE_GROUP)}
    ------------------------
    
    """
    logger.info(settings_message)
    print(inspect.cleandoc(settings_message))

    answer = ask_user(
        "DO THE ABOVE SETTINGS LOOK CORRECT? Ensure Panorama candidate config state is as desired as well! (y/n): "
    )

    if answer in ("no", "n"):
        print("Exiting..")
        sys.exit()
    print("\n\n")


def ask_user(question: str):
    answer = ""
    while answer.lower() not in ("y", "n", "yes", "no"):
        answer = input(question)
    return answer.lower()


async def get_objects_panorama(
    pan: PanoramaApi, names_only: bool = True, shared: bool = False
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
    pan: PanoramaApi, object_type: str, names_only: bool = True, shared: bool = False
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


async def get_objects_xml(configstr, obj_type=None, deep=None) -> Dict:
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

#
# def get_sec_rules_xml(configstr: str, object_type: str) -> Set:
#     """
#     Get objects from xml file instead of Panorama
#
#     Args:
#         configstr: xml filename
#         deep: deep search or not
#     Returns:
#          Dict/list of objects
#     Raises:
#         N/A
#     """
#     try:
#         config = etree.fromstring(configstr)
#     except XMLSyntaxError as exc:
#         print(exc)
#         print("\nInvalid XML File...try again! Our best guess is up there ^^^\n")
#         sys.exit(1)
#
#     try:
#         config.xpath("./devices/entry[@name='localhost.localdomain']/device-group")
#     except XPathEvalError as exc:
#         print(exc)
#         print(dir(exc))
#         print("\nInvalid XML File...try again! Our best guess is up there ^^^\n")
#         sys.exit(1)
#
#     # Get device groups and compare/merge with settings.py
#     #await set_device_groups(config=config, deep=deep)
#
#     # Get Security Rules
#     dg = "All-Devices"
#     object_xpath = None
#     if object_type == "pre":
#         object_xpath = f"./devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/pre-rulebase/security/rules/entry"
#     if object_type == "post":
#         object_xpath = f"./devices/entry[@name='localhost.localdomain']/device-group/entry[@name='{dg}']/post-rulebase/security/rules/entry"
#
#     # Get object
#     objs = config.xpath(object_xpath)
#
#     if not objs:
#         print(f"No {object_type} found in {dg}, moving on...")
#         my_objs = set([])
#
#     else:
#         my_objs = objs
#
#     return my_objs


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
                            # print(
                            #     f"Deep check found {temp1.get('@name')} in {temp1.get('@device-group')} and {temp2.get('@name')} in {temp2.get('@device-group')}"
                            # )
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
            if obj_name in shared_objs[object_type]["shared"]:
                # print(f"\n\tFound duplicate in shared: {obj_name}")
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
    pan: PanoramaApi,
    results: Dict,
    object_types: List[str],
    objs_list: Any,
    set_output: bool,
) -> Union[None, Tuple]:
    """
    Create the objects

    Args:
        pan: PanoramaApi object
        results: objects (duplicates) to be created (as part of 'move')
        object_types: object types to be created (used to create objects before groups)
        objs_list: full object values so that we can clone them
        set_output: set commands or not?

    """
    coroutines = []
    limit = asyncio.Semaphore(value=settings.MAX_CONCURRENT)
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
                        limit=limit,
                        object_type=object_type,
                        obj=dupe_obj,
                        device_group=settings.NEW_PARENT_DEVICE_GROUP,
                        set_output=set_output,
                    )
                )

    return await asyncio.gather(*coroutines)


async def do_the_deletes(
    pan: PanoramaApi, results: Dict, object_types: List[str], set_output: bool
) -> Union[None, Tuple]:
    """
    Delete the objects

    Args:
        pan: PanoramaApi object
        results: objects (duplicates) to be deleted
        object_types: object types to be deleted (used to send groups in before objects)
        set_output: set commands or not?

    """
    limit = asyncio.Semaphore(value=settings.MAX_CONCURRENT)
    coroutines = []
    for object_type in object_types:
        if results.get(object_type):
            for dupe, device_groups in results[object_type].items():
                for group in device_groups:
                    if group in settings.NEW_PARENT_DEVICE_GROUP:  # do this better?
                        continue
                    coroutines.append(
                        pan.delete_object(
                            limit=limit,
                            object_type=object_type,
                            name=dupe,
                            device_group=group,
                            set_output=set_output,
                        )
                    )

    return await asyncio.gather(*coroutines)


async def do_the_deletes_shared(
    pan: PanoramaApi, objects: Dict, object_types: List[str], set_output: bool
) -> Union[None, Tuple]:
    """
    Delete the shared objects

    Args:
        pan: PanoramaApi object
        objects: objects (duplicates) to be deleted
        object_types: object types to be deleted (used to send groups in before objects)
        set_output: set commands or not?
    """
    limit = asyncio.Semaphore(value=settings.MAX_CONCURRENT)
    coroutines = []
    params = {"location": "shared"}
    for object_type in object_types:
        if objects.get(object_type):
            for dupe in objects[object_type]:
                coroutines.append(
                    pan.delete_object(
                        limit=limit,
                        object_type=object_type,
                        name=dupe,
                        params=params,
                        set_output=set_output,
                    )
                )

    return await asyncio.gather(*coroutines)


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
    with open(f"{filename}-{dt}.json", "w", encoding="utf8") as fout:
        fout.write(json_str)
