import pytest

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


def test_check_sec_rules():
    rules = [
        {
            "@name": "rule1",
            "action": "permit",
            "from": {"member": ["inside"]},
            "source": {"member": ["1.1.1.1/32"]},
            "destination": {"member": ["9.9.9.9/32"]},
            "@loc": "test",
            "@device-group": "test",
            "service": {"member": ["test"]},
            "application": {"member": ["test"]},
        },
        {
            "@name": "rule2",
            "action": "permit",
            "from": {"member": ["inside"]},
            "source": {"member": ["2.2.2.2/32"]},
            "destination": {"member": ["9.9.9.9/32"]},
            "@loc": "test",
            "@device-group": "test",
            "service": {"member": ["test"]},
            "application": {"member": ["test"]},
        },
        {
            "@name": "rule3",
            "action": "permit",
            "from": {"member": ["inside"]},
            "source": {"member": ["3.3.3.3/32"]},
            "destination": {"member": ["9.9.9.9/32"]},
            "@loc": "test",
            "@device-group": "test",
            "service": {"member": ["test"]},
            "application": {"member": ["test"]},
        },
        {
            "@name": "rule4",
            "action": "permit",
            "from": {"member": ["inside"]},
            "source": {"member": ["4.4.4.4/32"]},
            "destination": {"member": ["9.9.9.9/32"]},
            "@loc": "test",
            "@device-group": "test",
            "service": {"member": ["test"]},
            "application": {"member": ["test"]},
        },
    ]

    correct_cmds = ["set device-group test pre-rulebase security rules 'rule1' source 2.2.2.2/32", "delete device-group test pre-rulebase security rules 'rule2'", "set device-group test pre-rulebase security rules 'rule1' source 3.3.3.3/32", "delete device-group test pre-rulebase security rules 'rule3'", "set device-group test pre-rulebase security rules 'rule1' source 4.4.4.4/32", "delete device-group test pre-rulebase security rules 'rule4'", '\n']
    from rich.pretty import pprint
    updates = utils.check_sec_rules(rules)
    #pprint(updates)
    cmds = utils.create_set_rule_output(updates, "pre")

    assert cmds == correct_cmds


def test_bunch_commands():
    test_set_commands = {
        "tags": [
            "set device-group All-Devices tag 'tag1' color color1",
            "set device-group All-Devices tag 'tag 2' color color2",
            "delete device-group dg1 tag 'tag1'",
            "delete shared tag 'tag1'",
        ],
        "addresses": [
            "set device-group All-Devices address '1.1.1.1' ip-netmask 1.1.1.1/32",
            "set device-group All-Devices address 'all ones' ip-netmask 1.1.1.1/32",
            "set device-group All-Devices address 'test-fqdn' fqdn a.example.com",
            "set device-group All-Devices address 'addr-tagged' tag 'tag1' ip-netmask 1.1.1.1/32",
            "set device-group All-Devices address 'addr-tagged2' tag [ 'tag1' 'tag2' ] ip-netmask 1.1.1.1/32",
            "delete device-group dg1 address '1.1.1.1'",
            "delete device-group dg1 address 'all ones'",
            "delete device-group dg1 address 'test-fqdn'",
            "delete shared address '1.1.1.1'",
            "delete shared address 'all ones'",
            "delete shared address 'test-fqdn",
        ],
        "services": [
            "set device-group All-Devices service 'tcp-443' protocol tcp port 443",
            "set device-group All-Devices service 'udp-443' protocol udp port 443",
            "set device-group All-Devices service 'src-40' protocol tcp source-port 40",
            "set device-group All-Devices service 'src-40 dst 443' protocol tcp source-port 40 port 443",
            "delete device-group dg2 service 'tcp-443'",
            "delete device-group dg2 service 'src-40 dst 443'",
        ],
        "address-groups": [
            "set device-group All-Devices address-group '2.2.2.2' static '2.2.2.2/32'",
            "set device-group All-Devices address-group 'addr group' static [ '1.1.1.1' '2.2.2.2' ]",
            "set device-group All-Devices address-group dynamic filter 'myfilter'",
            "delete device-group dg3 address-group 'addr group'",
        ],
        "service-groups": [
            "set device-group All-Devices service-group 'tcp-udp-443' members [ 'tcp-443' 'udp-443' ]",
            "delete shared service-group 'tcp-udp-443'",
        ],
    }
    correct_set_output = {
        "tags": {
            "tag1": [
                "set device-group All-Devices tag 'tag1' color color1",
                "delete device-group dg1 tag 'tag1'",
                "delete shared tag 'tag1'",
            ],
            "tag 2": ["set device-group All-Devices tag 'tag 2' color color2"],
        },
        "addresses": {
            "1.1.1.1": [
                "set device-group All-Devices address '1.1.1.1' ip-netmask 1.1.1.1/32",
                "delete device-group dg1 address '1.1.1.1'",
                "delete shared address '1.1.1.1'",
            ],
            "all ones": [
                "set device-group All-Devices address 'all ones' ip-netmask 1.1.1.1/32",
                "delete device-group dg1 address 'all ones'",
                "delete shared address 'all ones'",
            ],
            "test-fqdn": [
                "set device-group All-Devices address 'test-fqdn' fqdn a.example.com",
                "delete device-group dg1 address 'test-fqdn'",
            ],
            "addr-tagged": [
                "set device-group All-Devices address 'addr-tagged' tag 'tag1' ip-netmask 1.1.1.1/32",
            ],
            "addr-tagged2": [
                "set device-group All-Devices address 'addr-tagged2' tag [ 'tag1' 'tag2' ] ip-netmask 1.1.1.1/32",
            ],
        },
        "services": {
            "tcp-443": [
                "set device-group All-Devices service 'tcp-443' protocol tcp port 443",
                "delete device-group dg2 service 'tcp-443'",
            ],
            "udp-443": [
                "set device-group All-Devices service 'udp-443' protocol udp port 443"
            ],
            "src-40": [
                "set device-group All-Devices service 'src-40' protocol tcp source-port 40"
            ],
            "src-40 dst 443": [
                "set device-group All-Devices service 'src-40 dst 443' protocol tcp source-port 40 port 443",
                "delete device-group dg2 service 'src-40 dst 443'",
            ],
        },
        "address-groups": {
            "2.2.2.2": [
                "set device-group All-Devices address-group '2.2.2.2' static '2.2.2.2/32'"
            ],
            "addr group": [
                "set device-group All-Devices address-group 'addr group' static [ '1.1.1.1' '2.2.2.2' ]",
                "delete device-group dg3 address-group 'addr group'",
            ],
        },
        "service-groups": {
            "tcp-udp-443": [
                "set device-group All-Devices service-group 'tcp-udp-443' members [ 'tcp-443' 'udp-443' ]",
                "delete shared service-group 'tcp-udp-443'",
            ]
        },
    }
    output = utils.bunch_commands(test_set_commands)
    assert output == correct_set_output


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
        "objs_list": {
            "addresses": {
                "dg1": [{"ip-netmask": "10.1.1.0/24", "@name": "testobj"}],
                "dg2": [{"ip-netmask": "nope"}],
            }
        },
        "object_type": "addresses",
        "device_group": "dg1",
        "name": "testobj",
    }

    obj = utils.find_object(**my_args)
    assert obj == {"ip-netmask": "10.1.1.0/24", "@name": "testobj"}

    my_broken_args = my_args
    my_broken_args["objs_list"] = {
        "addresses": {
            "dg1": {"ip-netmask": "10.1.1.0/24", "@name": "testobj"},
            "dg2": [{"ip-netmask": "nope"}],
        }
    }

    with pytest.raises(SystemExit) as error:
        obj = utils.find_object(**my_broken_args)
    assert error.value.code == 1


if __name__ == "__main__":
    # test_bunch_commands()
    test_check_sec_rules()
