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
