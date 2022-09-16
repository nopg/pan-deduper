"""pan_deduper.panorama_api"""
import asyncio
import logging
import sys
from typing import Any, Dict, List, Union, Tuple

import httpx
from lxml import etree

from pan_deduper import settings

API_VERSION = "v10.1"
logger = logging.getLogger("utils")


class Panorama_api:
    """Panorama api"""

    def __init__(self, panorama: str, username: str, password: str) -> None:
        """
        Initialize Panorama API Object

        Args:
            panorama: Panorama IP/FQDN
            username: username
            password: password
        Returns:
            N/A
        Raises:
            N/A
        """
        self.session: Dict[str, Any] = {}
        self.panorama = panorama
        self.username = username
        self.password = password
        self.base_url = f"https://{panorama}/restapi/{API_VERSION}/"
        self.apikey = ""
        self.login_data = {}

    async def login(self) -> None:
        """
        Login to Panorama

        Args: N/A
        Returs: None
        Raises: ?
        """
        sess = httpx.AsyncClient(verify=False)  # Disable certificate verification
        params = {"type": "keygen", "user": self.username, "password": self.password}
        url = f"https://{self.panorama}/api/"

        try:
            response = await sess.get(url=url, params=params)
        except httpx.RequestError as e:
            print(f"{url=}")
            print("Request error: ", e)
            sys.exit()
        except httpx.HTTPStatusError as e:
            print(f"{url=}")
            print("HTTP Status error: ", e)
            sys.exit()

        xml = etree.fromstring(response.text)
        key = xml.find(".//key")

        if key is not None:
            self.apikey = key.text
            self.session[self.apikey] = sess
            self.login_data = {"X-PAN-KEY": self.apikey}
        else:
            print(f"Response was: {response.text}")
            print("Unable to retrieve API key...bad credentials?")
            sys.exit(1)

    async def get_request(self, url: str, headers: Dict = None, params: Dict = None):
        """
        Generic GET Request

        Args:
            url: URL String for endpoint/route to tickle
            headers: headers (mainly for authentication)
            params: parameters (if any)
        Returns: json?
        Raises: ?
        """

        url = self.base_url + url
        headers = self.login_data if not headers else self.login_data.update(headers)

        try:
            response = await self.session[self.apikey].get(
                url=url, headers=headers, params=params
            )
            return response.json()
        except httpx.RequestError as e:
            print("Request error: ", e.request)
            logger.error(f"Error getting {url}.")
        except httpx.HTTPStatusError as e:
            print(f"{url=}")
            print("HTTP Status error: ", e)
            sys.exit()

    async def post_request(
        self, url: str, data: Dict, headers: Dict = None, params: Dict = None
    ):
        """
        Generic POST Request

        Args:
            url: URL String for endpoint/route to tickle
            headers: headers (mainly for authentication)
            params: parameters (if any)
            data: dictionary of object to create
        Returns: json?
        Raises: ?
        """

        url = self.base_url + url
        headers = self.login_data if not headers else self.login_data.update(headers)

        try:
            response = await self.session[self.apikey].post(
                url=url, headers=headers, params=params, json=data, timeout=120
            )
            return response.json()
        except httpx.RequestError as e:
            print("Request error: ", e.request)
            logger.error(f"Request Error: {url}.")
        except httpx.HTTPStatusError as e:
            print(f"{url=}")
            print("HTTP Status error: ", e)
            sys.exit()

    async def delete_request(self, url: str, headers: Dict = None, params: Dict = None):
        """
        Generic DELETE Request

        Args:
            url: URL String for endpoint/route to tickle
            headers: headers (mainly for authentication)
            params: parameters (if any)
            data: dictionary of object to create
        Returns: json?
        Raises: ?
        """

        url = self.base_url + url
        headers = self.login_data if not headers else self.login_data.update(headers)

        try:
            response = await self.session[self.apikey].delete(
                url=url, headers=headers, params=params, timeout=120
            )
            return response.json()
        except httpx.RequestError as e:
            print("Request error: ", e.request)
            logger.error(f"Request Error: {url}.")
        except httpx.HTTPStatusError as e:
            print(f"{url=}")
            print("HTTP Status error: ", e)
            sys.exit()

    async def get_device_groups(self):
        response = await self.get_request(url="Panorama/DeviceGroups")
        if int(response.get("result").get("@count")) > 0:
            return [
                name["@name"] for name in response["result"]["entry"]
            ]  # Just return list of names

        print("No Device Groups found..whatchu doing?")
        sys.exit(1)

    async def get_parent_dgs(self):
        url = f"https://{self.panorama}/api/"
        xpath = (
            "/config/readonly/devices/entry[@name='localhost.localdomain']/device-group"
        )
        params = {"type": "config", "action": "get", "xpath": xpath, "key": self.apikey}
        try:
            response = await self.session[self.apikey].get(url=url, params=params)
        except httpx.RequestError as e:
            print("Request error: ", e.request)
            logger.error(f"Request Error: {url}.")
        except httpx.HTTPStatusError as e:
            print(f"{url=}")
            print("HTTP Status error: ", e)
            sys.exit()

        parent_dgs = {}
        xml = etree.fromstring(response.text)
        dgs = xml.xpath("result/device-group/entry")
        if not dgs:
            print("XML error getting parent device groups")
            sys.exit()
        for dg in dgs:
            dg_name = dg.get("name")
            parent = dg.find("parent-dg")

            if parent is not None:
                if parent == "shared":
                    continue
                parent_dgs[dg_name] = parent.text
            else:
                parent_dgs[dg_name] = None
        return parent_dgs

    async def get_objects(
        self, object_type: str, device_group: str = None, params: Dict = None
    ):
        """
        Get Objects from API

        Args:
            object_type: addresses/groups/service/groups
            device_group:   device group
            params: parameters on where to get objects from
        Returns:
             Dict of objects
        Raises:
            N/A
        """
        if not params:
            params = {"location": "device-group", "device-group": f"{device_group}"}

        if object_type == "addresses":
            url = "Objects/Addresses"
        elif object_type == "address-groups":
            url = "Objects/AddressGroups"
        elif object_type == "services":
            url = "Objects/Services"
        elif object_type == "service-groups":
            url = "Objects/ServiceGroups"
        elif object_type == "tags":
            url = "Objects/Tags"
        else:
            print(f"Unsupported object_type sent: {object_type}")
            sys.exit(0)

        response = await self.get_request(url=url, params=params)
        if not response.get("result"):
            logger.error(f"Failed getting object via: {url}")
            logger.error(f"Failed above, parameters: {params}")
        elif int(response.get("result").get("@count")) > 0:
            return response["result"]["entry"]

        return None

    async def delete_object(self, limit, **kwargs) -> Union[None, Tuple]:
        async with limit:
            result = await self._delete_object(**kwargs)
            return result

    async def _delete_object(
        self, object_type: str, name: str, set_output: bool, device_group: str = None, params: Dict = None,
    ) -> Union[None, Tuple]:
        """
        Delete objects

        Args:
            object_type: object type.. (address/group/service/groups)
            name:   name of object
            device_group:   device group..
            params: params (shared)
        Returns:
             response message (dict)
        Raises:
            N/A
        """
        if object_type == "addresses":
            url = "Objects/Addresses"
        elif object_type == "address-groups":
            url = "Objects/AddressGroups"
        elif object_type == "services":
            url = "Objects/Services"
        elif object_type == "service-groups":
            url = "Objects/ServiceGroups"
        elif object_type == "tags":
            url = "Objects/Tags"
        else:
            print(f"Unsupported object_type sent: {object_type}")
            sys.exit(0)
        if not params:
            params = {
                "location": "device-group",
                "device-group": f"{device_group}",
                "name": name,
            }
        else:
            device_group = "shared"
            params["name"] = name

        if set_output:
            return self.delete_set_output(name=name, device_group=device_group, object_type=object_type)

        # logger.info(f"starting to delete {name}.")
        response = await self.delete_request(url=url, params=params)

        if response:
            if response.get("@code") == "20":
                logger.info(f"Deleted {object_type}:{name} from {device_group}.")
            else:
                logger.error(
                    f"Failed to delete {object_type}:{name} from {device_group}:"
                )
                logger.error(response["message"])
        else:
            logger.error(f"Failed to delete {object_type}:{name} from {device_group}:")

        return None

    async def create_object(self, limit, **kwargs) -> Union[None, Tuple]:
        async with limit:
            result = await self._create_object(**kwargs)
            return result

    async def _create_object(self, object_type: str, obj: Dict, device_group: List, set_output: bool) -> Union[None, str]:
        """
        Create object

        Args:
            object_type:
            obj:
            device_group:
        Returns:
             response message (dict)
        """
        remove_keys = ["@location", "@device-group", "@loc", "@overrides"]

        if object_type == "addresses":
            url = "Objects/Addresses"
        elif object_type == "address-groups":
            url = "Objects/AddressGroups"
        elif object_type == "services":
            url = "Objects/Services"
        elif object_type == "service-groups":
            url = "Objects/ServiceGroups"
        elif object_type == "tags":
            url = "Objects/Tags"
        else:
            print(f"Unsupported object_type sent: {object_type}")
            sys.exit(0)

        for group in device_group:
            params = {
                "location": "device-group",
                "device-group": f"{group}",
                "name": obj["@name"],
            }

            for k in remove_keys:
                if obj.get(k):
                    obj.pop(k)

            obj = {"entry": obj}    # Still has ['entry'], fix later

            if set_output:
                return self.create_set_output(obj=obj["entry"], device_group=group, object_type=object_type)

            # logger.info(f"starting to create {obj['entry']['@name']}.")
            response = await self.post_request(url=url, params=params, data=obj)

            if response:
                if response.get("@code") == "20":
                    logger.info(
                        f"Created {object_type}:{obj['entry']['@name']} in {group}."
                    )
                else:
                    logger.error(
                        f"Failed to create {object_type}:{obj['entry']['@name']} in {group}:"
                    )
                    logger.error(response["message"])
            else:
                logger.error(
                    f"Failed to create {object_type}:{obj['entry']['@name']} in {group}:"
                )

    @staticmethod
    def format_object_type(object_type: str):
        if object_type == "addresses":
            object_type_formatted = "address"
        elif object_type == "address-groups":
            object_type_formatted = "address-group"
        elif object_type == "services":
            object_type_formatted = "service"
        elif object_type == "service-groups":
            object_type_formatted = "service"
        elif object_type == "tags":
            object_type_formatted = "tag"
        else:
            print(f"Unsupported object type {object_type}")
            sys.exit()
        return object_type_formatted

    @staticmethod
    def create_set_output(obj, device_group, object_type):
        obj_type_formatted = Panorama_api.format_object_type(object_type=object_type)

        set_cmd = f"set device-group {device_group} {obj_type_formatted} '{obj['@name']}' "

        if obj.get("tag"):
            set_cmd += f"tag '{obj['tag']}' "
        if obj.get("description"):
            set_cmd += f"description '{obj['description']}' "

        if object_type == "addresses":
            if obj.get("fqdn"):
                set_cmd += f"fqdn {obj['fqdn']}"
            elif obj.get("ip-netmask"):
                set_cmd += f"ip-netmask {obj['ip-netmask']}"
            elif obj.get("ip-range"):
                set_cmd += f"ip-range {obj['ip-range']}"
            elif obj.get("ip-wildcard"):
                set_cmd += f"ip-wildcard {obj['ip-wildcard']}"

        elif object_type == "address-groups":
            if obj.get("dynamic"):
                pa_filter = obj["dynamic"]["filter"]
                set_cmd += f"dynamic filter {pa_filter}"
            elif obj.get("static"):
                members = obj["static"]["member"]
                if len(members) == 1:
                    set_cmd += f"{members[0]}"
                else:
                    set_cmd += "[ "
                    for member in members:
                        set_cmd += f"'{member}' "
                    set_cmd += "]"

        elif object_type == "services":
            protocol = obj["protocol"]
            tcp_udp = next(iter(protocol))  # First key will be either 'tcp' or 'udp'
            ports = protocol[tcp_udp]

            set_cmd += f"{tcp_udp} "
            if ports.get("source-port"):
                set_cmd += f"source-port {ports['source-port']} "
            set_cmd += f"port {ports['port']}"

        elif object_type == "service-groups":
            set_cmd += f"members [ "
            members = obj["members"]
            for member in members:
                set_cmd += f"'{member}' "
            set_cmd += "]"
        elif object_type == "tags":
            if obj.get("comments"):
                set_cmd += f"comments '{obj['comments']}' "
            if obj.get("color"):
                set_cmd += f"color {obj['color']}"

        return set_cmd

    @staticmethod
    def delete_set_output(name, device_group, object_type):
        obj_type_formatted = Panorama_api.format_object_type(object_type=object_type)
        if device_group == "shared":
            set_cmd = f"delete {device_group} {obj_type_formatted} {name}"
        else:
            set_cmd = f"delete device-group {device_group} {obj_type_formatted} {name}"

        return set_cmd
