import os

import pytest

from pan_deduper.panorama_api import PanoramaApi as pa_api


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


test_objs = {
    "addresses": [
        {"@name": "addr1", "ip-netmask": "1.1.1.1/24"},
        {"@name": "addr two", "ip-netmask": "2.2.2.2"},
        {"@name": "3.3.3.0/25", "ip-range": "3.3.3.0-3.3.3.127"},
    ],
    "address-groups": [
        {
            "@name": "grp1",
            "description": "my description",
            "static": {"member": ["member1"]},
        },
        {"@name": "grp2", "static": {"member": ["member1", "member2", "member 3"]}},
    ],
    "services": [
        {"@name": "tcp-443", "protocol": {"tcp": {"port": 443}}},
        {"@name": "udp-443", "protocol": {"udp": {"source-port": 22, "port": 443}}},
    ],
    "service-groups": [
        {
            "@name": "svc-grp1",
            "members": {"member": ["tcp-443", "udp-443"]},
            "tags": {"member": ["tag1"]},
        }
    ],
}

correct_set_commands_create = {
    "addresses": [
        "set device-group dg1 address 'addr1' ip-netmask 1.1.1.1/24",
        "set device-group dg1 address 'addr two' ip-netmask 2.2.2.2",
        "set device-group dg1 address '3.3.3.0/25' ip-range 3.3.3.0-3.3.3.127",
    ],
    "address-groups": [
        "set device-group dg1 address-group 'grp1' description 'my description' 'member1'",
        "set device-group dg1 address-group 'grp2' [ 'member1' 'member2' 'member 3' ]",
    ],
    "services": [
        "set device-group dg1 service 'tcp-443' protocol tcp port 443",
        "set device-group dg1 service 'udp-443' protocol udp source-port 22 port 443",
    ],
    "service-groups": [
        "set device-group dg1 service-group 'svc-grp1' members [ 'tcp-443' 'udp-443' ]"
    ],
}

correct_set_commands_delete = {
    "addresses": [
        "delete device-group dg1 address 'addr1'",
        "delete device-group dg1 address 'addr two'",
        "delete device-group dg1 address '3.3.3.0/25'",
    ],
    "address-groups": [
        "delete device-group dg1 address-group 'grp1'",
        "delete device-group dg1 address-group 'grp2'",
    ],
    "services": [
        "delete device-group dg1 service 'tcp-443'",
        "delete device-group dg1 service 'udp-443'",
    ],
    "service-groups": ["delete device-group dg1 service-group 'svc-grp1'"],
}


def test_creates():
    output = {}
    for obj_type, objs in test_objs.items():
        output[obj_type] = []
        for obj in objs:
            if obj:
                _ = pa_api.create_set_output(
                    obj=obj, device_group="dg1", object_type=obj_type
                )
                output[obj_type].append(_)
    assert output == correct_set_commands_create


def test_deletes():
    output = {}
    for obj_type, objs in test_objs.items():
        output[obj_type] = []
        for obj in objs:
            if obj:
                _ = pa_api.delete_set_output(
                    name=obj["@name"], device_group="dg1", object_type=obj_type
                )
                output[obj_type].append(_)
    assert output == correct_set_commands_delete


if __name__ == "__main__":
    test_creates()
