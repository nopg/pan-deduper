import pytest
from lxml.etree import XMLSyntaxError

import pan_deduper.settings as settings
import pan_deduper.utils as utils


def test_format_objs_names_only():
    settings.EXISTING_PARENT_DGS = {}
    objs = [
        {"@name": "obj1", "@loc": "test", "ip-netmask": "10.1.1.0/24"},
        {"@name": "obj2", "@loc": "test", "ip-netmask": "10.2.2.0/24"},
    ]
    fmt_objs = utils.format_objs(objs=objs, device_group="test", names_only=True)
    assert isinstance(fmt_objs, set)


def test_format_objs_full():
    settings.EXISTING_PARENT_DGS = {}
    objs = [
        {"@name": "obj1", "@loc": "test", "ip-netmask": "10.1.1.0/24"},
        {"@name": "obj2", "@loc": "test", "ip-netmask": "10.2.2.0/24"},
    ]
    fmt_objs = utils.format_objs(objs=objs, device_group="test", names_only=False)
    assert isinstance(fmt_objs, list)


def test_find_object():
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
    my_args = {
        "objs_list" : {"addresses":{"dg1":[{'hi': 'lo', '@name': 'hi'}], "dg2": [{"no": 'hi'}]}},
        "object_type" : "addresses",
        "device_group" :"dg1",
        "name" : "hi",
    }

    obj = utils.find_object(**my_args)
    assert obj == {"hi": "lo", "@name": "hi"}

    my_broken_args = my_args
    my_broken_args["objs_list"] = {"addresses":{"dg1":{'hi': 'lo', '@name': 'hi'}, "dg2": [{"no": 'hi'}]}}

    with pytest.raises(SystemExit) as error:
        obj = utils.find_object(**my_broken_args)
    assert error.value.code == 1
