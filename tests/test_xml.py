import sys

import pytest
from lxml.etree import XMLSyntaxError

import pan_deduper.utils as utils


@pytest.mark.asyncio
async def test_bad_xml(capsys):
    bad_xml = "<hi><no></bad>"
    with pytest.raises(SystemExit) as error:
        objs = await utils.get_objects_xml(bad_xml)
    assert error.value.code == 1
    msg = capsys.readouterr()
    assert msg.out.endswith(
        "Invalid XML File...try again! Our best guess is up there ^^^\n\n"
    )


@pytest.mark.asyncio
async def test_empty_xml(capsys):
    empty_xml = "<hi><no></no></hi>"
    with pytest.raises(SystemExit) as error:
        objs = await utils.get_objects_xml(empty_xml)
    assert error.value.code == 1
    msg = capsys.readouterr()
    assert msg.out.endswith(
        "Invalid XML File...try again! Our best guess is up there ^^^\n\n"
    )
