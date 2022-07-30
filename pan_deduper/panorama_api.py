import logging
import sys
from typing import Any, Dict

import httpx
from lxml import etree

API_VERSION = "v10.1"
logger = logging.getLogger("utils")


class Panorama_api:
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
        self.APIKEY = ""
        self.login_data = {}

    async def login(self) -> None:
        """
        Login to Panorama

        Args: N/A
        Returs: None
        Raises: ?
        """
        sess = httpx.AsyncClient(verify=False)  # Disable certificate verification
        url = f"https://{self.panorama}/api/?type=keygen&user={self.username}&password={self.password}"

        try:
            response = await sess.get(url=url)
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
            self.APIKEY = key.text
            self.session[self.APIKEY] = sess
            self.login_data = {"X-PAN-KEY": self.APIKEY}
        else:
            print("Unable to retrieve API key...bad credentials?")
            print(f"Response was: {response.text}")
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
            response = await self.session[self.APIKEY].get(
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
            response = await self.session[self.APIKEY].post(
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
            response = await self.session[self.APIKEY].delete(
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
        else:
            print(f"Unsupported object_type sent: {object_type}")
            sys.exit(0)

        response = await self.get_request(url=url, params=params)
        if int(response.get("result").get("@count")) > 0:
            return response["result"]["entry"]

        return None

    async def delete_object(
        self, object_type: str, name: str, device_group: str = None, params: Dict = None
    ):
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

        response = await self.delete_request(url=url, params=params)

        if response:
            if response["@code"] == "20":
                logger.info(f"Deleted {object_type}:{name} from {device_group}.")
            else:
                logger.error(
                    f"Failed to delete {object_type}:{name} from {device_group}:"
                )
                logger.error(response["message"])
        else:
            logger.error(f"Failed to delete {object_type}:{name} from {device_group}:")

        return None

    async def create_object(self, object_type: str, obj: Dict, device_group: str):
        """
        Create object

        Args:
            object_type:
            obj:
            device_groups:
        Returns:
             response message (dict)
        Raises:
            N/A
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
        else:
            print(f"Unsupported object_type sent: {object_type}")
            sys.exit(0)

        for dg in device_group:
            params = {
                "location": "device-group",
                "device-group": f"{dg}",
                "name": obj["@name"],
            }

            for k in remove_keys:
                if obj.get(k):
                    obj.pop(k)

            obj = {"entry": obj}

            response = await self.post_request(url=url, params=params, data=obj)

            if response:
                if response["@code"] == "20":
                    logger.info(
                        f"Created {object_type}:{obj['entry']['@name']} in {dg}."
                    )
                else:
                    logger.error(
                        f"Failed to create {object_type}:{obj['entry']['@name']} in {dg}:"
                    )
                    logger.error(response["message"])
            else:
                logger.error(
                    f"Failed to create {object_type}:{obj['entry']['@name']} in {dg}:"
                )
            return obj
