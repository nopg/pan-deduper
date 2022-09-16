import os

import pytest

from pan_deduper.panorama_api import Panorama_api as pa_api

test_objs_services = [
    {"@name": "tcp-443", "protocol": {"tcp": {"port": 443}}},
    {"@name": "udp-443", "protocol": {"udp": {"source-port": 22, "port": 443}}},
]

test_objs_addr_groups = [
    {"@name": "grp1", "description": "my description", "static": {"member": ["member1"]}},
    {"@name": "grp2", "static": {"member": ["member1", "member2", "member 3"]}}
]


@pytest.fixture(scope="module")
def vcr_config():
    return {"filter_query_parameters": ["user", "password"]}


@pytest.mark.asyncio
# @pytest.mark.vcr()
async def test_correct_pan_login():
    login_info = {
        "panorama": os.environ.get("PANORAMA_IP"),
        "username": os.environ.get("PAN_USERNAME"),
        "password": os.environ.get("PAN_PASSWORD"),
    }
    pa = pa_api(**login_info)
    await pa.login()
    assert pa.apikey is not None


@pytest.mark.asyncio
# @pytest.mark.vcr()
async def test_incorrect_pan_login(capsys):
    login_info = {
        "panorama": "10.254.254.5",
        "username": "admin",
        "password": "admin",
    }
    with pytest.raises(SystemExit) as error:
        pa = pa_api(**login_info)
        await pa.login()
    assert error.value.code == 1
    msg = capsys.readouterr()
    assert msg.out.endswith("Unable to retrieve API key...bad credentials?\n")


def test_create_set_output():
    for obj in test_objs_services:
        test_obj_create = {"obj": obj, "device_group": "dg1", "object_type": "services"}
        print(pa_api.create_set_output(**test_obj_create))
    for obj in test_objs_addr_groups:
        test_obj_create = {"obj": obj, "device_group": "dg2", "object_type": "address-groups"}
        print(pa_api.create_set_output(**test_obj_create))


def test_delete_set_output():
    for obj in test_objs_services:
        test_obj_delete = {
            "name": obj["@name"],
            "device_group": "dg1",
            "object_type": "addresses",
        }
        print(pa_api.delete_set_output(**test_obj_delete))


if __name__ == "__main__":
    test_create_set_output()
    test_delete_set_output()
