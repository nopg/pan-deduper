"""
Description: 
    XML API Library to be used with the Palo Alto API

Requires:
    requests
    xmltodict
    json
        to install try: pip3 install xmltodict requests json

Author:
    Ryan Gillespie rgillespie@compunet.biz
    Docstring stolen from Devin Callaway

Tested:
    Tested on macos 10.12.3
    Python: 3.6.2
    PA VM100

Example usage:
        import xml_api_lib_pa as pa
        # export example:
        obj = pa.get_xml_request_pa(call_type="config",action="show",xpath="")
        # import example:
        obj = pa.get_xml_request_pa(call_type="config",action="set",xpath="..",element="<../>")

Cautions:
    Future abilities will be added when use-cases warrant,
     currently ONLY supported for export/import operations (type=config,action=show, get, or set)

Legal:
    THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
    WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
    MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
    ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
    WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
    ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
    OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
"""

import json
import os
import sys
import xml.dom.minidom
from datetime import datetime

import requests
import xmltodict

# Who cares about SSL?
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

#########################################################################################################
DEBUG = False

# PA:
XPATH_ADDRESS_OBJ = "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/address"
XPATH_INTERFACES = (
    "/config/devices/entry[@name='localhost.localdomain']/network/interface"
)
XPATH_SECURITYRULES = "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/rulebase/security/rules"
XPATH_NAT_RULES = "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/rulebase/nat/rules"

# PAN:
XPATH_DEVICE_GROUPS = (
    "/config/devices/entry[@name='localhost.localdomain']/device-group"
)
XPATH_TEMPLATE_NAMES = "/config/devices/entry[@name='localhost.localdomain']/template"
XPATH_ADDRESS_OBJ_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/address"
XPATH_ADDRESS_GROUP_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/address-group"
XPATH_SERVICE_OBJ_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/service"
XPATH_SERVICE_GROUP_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/service-group"
XPATH_INTERFACES_PAN = "/config/devices/entry[@name='localhost.localdomain']/template/entry[@name='TEMPLATE_NAME']/config/devices/entry[@name='localhost.localdomain']/network/interface"
XPATH_SECURITY_RULES_PRE_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/pre-rulebase/security/rules"
XPATH_SECURITY_RULES_POST_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/post-rulebase/security/rules"
XPATH_NAT_RULES_PRE_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/pre-rulebase/nat/rules"
XPATH_NAT_RULES_POST_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/post-rulebase/nat/rules"
XPATH_CUSTOM_URL_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/profiles/custom-url-category"
XPATH_VIRUS_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/profiles/virus"
XPATH_FILE_BLOCKING_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/profiles/file-blocking"
XPATH_DECRYPTION_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/profiles/decryption"
XPATH_URL_FILTERING_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/profiles/url-filtering"
XPATH_SPYWARE_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/profiles/spyware"
XPATH_VULNERABILITY_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/profiles/vulnerability"
XPATH_WILDFIRE_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/profiles/wildfire-analysis"
XPATH_PROFILE_GROUP_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/profile-group"
XPATH_TAGS_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/tag"
XPATH_EDLS_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/external-list"
XPATH_SCHEDULE_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/schedule"
XPATH_APP_FILTER_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/application-filter"
XPATH_DOS_PROTECTION_PAN = "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']/profiles/dos-protection"
SHARED_REPLACE = "/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='DEVICE_GROUP']"
#########################################################################################################

# Menu to grab PA/Panorama Type
def get_pa_type():
    allowed = list("12")  # Allowed user input
    incorrect_input = True
    while incorrect_input:
        pa_type = input(
            """\nIs this a PA Firewall or Panorama?

        1) PA (Firewall)
        2) Panorama (PAN)

        Enter 1 or 2: """
        )

        for value in pa_type:
            if value not in allowed:
                incorrect_input = True
                break
            else:
                incorrect_input = False

    if pa_type == "1":
        pa_type = "pa"
    else:
        pa_type = "panorama"

    return pa_type


def create_xml_files(temp, filename):

    # Pull folder name from string
    end = filename.rfind("/")
    if end != -1:
        folder = filename[0:end]
        timestamp = (
            "/"
            + str(datetime.now().year)
            + "-"
            + str(datetime.now().month)
            + "-"
            + str(datetime.now().day)
            + "--"
            + str(datetime.now().hour)
            + "-"
            + str(datetime.now().minute)
            + "/"
        )

        filename = folder + timestamp + filename[end:]

        # Create the root folder and subfolder if it doesn't already exist
        os.makedirs(folder + timestamp, exist_ok=True)

    # Because XML: remove <response/><result/> and <?xml> tags
    # Using get().get() won't cause exception on KeyError
    # Check for various response type and ensure xml is written consistently

    # Set data
    if not isinstance(temp, list):
        data = temp.get("response")
        data = {"response": data}

        if data:
            # data = temp.get("response").get("result")
            if data:
                data = xmltodict.unparse(data)
            else:
                data = xmltodict.unparse(temp)
        else:
            data = xmltodict.unparse(temp)
        data = data.replace('<?xml version="1.0" encoding="utf-8"?>', "")

        prettyxml = xml.dom.minidom.parseString(data).toprettyxml()

        with open(filename, "w") as fout:
            fout.write(prettyxml)
    else:
        data = temp
        with open(filename, "w") as fout:
            fout.write("\n".join(data))


def create_json_files(temp, filename):
    """
    CREATE OUTPUT FILES

    :param data: list of data to be written
    :param template_type: 'feature' or 'device'
    :return: None, print output
    """
    # Pull folder name from string
    end = filename.rfind("/")
    folder = filename[0:end]

    timestamp = (
        "/"
        + str(datetime.now().year)
        + "-"
        + str(datetime.now().month)
        + "-"
        + str(datetime.now().day)
        + "--"
        + str(datetime.now().hour)
        + "-"
        + str(datetime.now().minute)
        + "/"
    )

    filename = folder + timestamp + filename[end:]

    # Create the root folder and subfolder if it doesn't already exist
    os.makedirs(folder + timestamp, exist_ok=True)

    data = json.dumps(temp, indent=4, sort_keys=True)
    # Write Data
    fout = open(filename, "w")
    fout.write(data)
    fout.close()

    # print("\tCreated: {}\n".format(filename))


# XML API Class for use with Palo Alto API
class api_lib_pa:
    # Upon creation:
    def __init__(self, pa_ip, username, password, pa_type):
        self.pa_ip = pa_ip
        self.username = username
        self.password = password
        self.pa_type = pa_type
        self.device_group = None
        self.template_name = None
        self.session = {}
        self.key = 0

        self.login(self.pa_ip, username, password)

    # Called from init(), login to the Palo Alto
    def login(self, pa_ip, username, password):

        # Create URL's
        base_url_str = f"https://{pa_ip}/"  # Base URL
        login_action = "/api?type=keygen"  # Get API Key
        login_data = f"&user={username}&password={password}"  # Format data for login
        login_url = (
            base_url_str + login_action + login_data
        )  # URL for posting login data

        # Create requests session
        sess = requests.session()

        # get API key
        login_response = sess.post(url=login_url, verify=False)

        # Login Failed check
        if login_response.status_code == 403:
            print("Login Failed")
            sys.exit(0)

        # Set successful session and key
        self.session[pa_ip] = sess
        temp = xmltodict.parse(login_response.text)
        self.key = temp.get("response").get("result").get("key")
        if not self.key:
            print(f"Login Failed: Response=\n{temp}")
            sys.exit(0)

    # Grab Panorama Device Groups & Templates
    def grab_panorama_objects(self):
        temp_device_groups = self.grab_api_output("xml", XPATH_DEVICE_GROUPS)
        temp_template_names = self.grab_api_output("xml", XPATH_TEMPLATE_NAMES)
        device_groups = []
        template_names = []

        # Need to check for no response, must be an IP not address
        if "entry" in temp_device_groups["result"]["device-group"]:
            for entry in temp_device_groups["result"]["device-group"]["entry"]:
                device_groups.append(entry["@name"])
        else:
            print(f"Error, Panorama chosen but no Device Groups found.")
            sys.exit(0)

        # Need to check for no response, must be an IP not address
        if "entry" in temp_template_names["result"]["template"]:
            if isinstance(temp_template_names["result"]["template"]["entry"], list):
                for entry in temp_template_names["result"]["template"]["entry"]:
                    template_names.append(entry["@name"])
            else:
                template_names.append(
                    temp_template_names["result"]["template"]["entry"]["@name"]
                )
        else:
            print(f"Error, Panorama chosen but no Template Names found.")
            sys.exit(0)

        return device_groups, template_names

    # GET request for Palo Alto API
    def get_xml_request_pa(
        self,
        call_type="config",
        action="show",
        xpath=None,
        element=None,
    ):
        # If no element is sent, should be a 'show' or 'get' action, do not send &element=<element>
        if not element:
            url = f"https://{self.pa_ip}:443/api?type={call_type}&action={action}&xpath={xpath}&key={self.key}"
        else:
            url = f"https://{self.pa_ip}:443/api?type={call_type}&action={action}&xpath={xpath}&key={self.key}&element={element}"

        # Make the API call
        response = self.session[self.pa_ip].get(url, verify=False)

        # Extra logging if debugging
        if DEBUG:
            print(f"URL = {url}")
            print(
                f"\nGET request sent: type={call_type}, action={action}, \n  xpath={xpath}.\n"
            )
            print(f"\nResponse Status Code = {response.status_code}")
            print(f"\nResponse = {response.text}")

        # Return string (XML)
        return response.text

    # GET request for Palo Alto API
    def get_rest_request_pa(self, restcall=None, element=None):
        headers = {"X-PAN-KEY": self.key}

        # If no element is sent, should be a 'show' or 'get' action, do not send &element=<element>
        if not element:
            url = f"https://{self.pa_ip}:443{restcall}"
        else:
            url = f"https://{self.pa_ip}:443{restcall}&element={element}"

        # Make the API call
        response = self.session[self.pa_ip].get(url, headers=headers, verify=False)

        # Extra logging if debugging
        if DEBUG:
            print(f"URL = {url}")
            print(f"\nGET request sent: restcall={restcall}.\n")
            print(f"\nResponse Status Code = {response.status_code}")
            print(f"\nResponse = {response.text}")

        # Return string (XML)
        return response.text

    # Import Named Configuration
    def import_named_configuration(
        self, xml_config, call_type="import", category="configuration"
    ):

        url = f"https://{self.pa_ip}:443/api?type={call_type}&category={category}&key={self.key}"

        # Make the API call
        response = self.session[self.pa_ip].post(
            url, files={"file": xml_config}, verify=False
        )

        # Extra logging if debugging
        if DEBUG:
            print(f"URL = {url}")
            print(f"\nGET request sent: type={call_type}, category={category}, \n")
            print(f"\nResponse Status Code = {response.status_code}")
            print(f"\nResponse = {response.text}")

        # Return response
        return response

    def grab_api_output(
        self,
        xml_or_rest,
        xpath_or_restcall,
        filename=None,
    ):
        # Grab PA/Panorama API Output
        success = False
        if xml_or_rest == "xml":

            response = self.get_xml_request_pa(
                call_type="config", action="get", xpath=xpath_or_restcall
            )
            xml_response = xmltodict.parse(response)

            if xml_response["response"]["@status"] == "success":
                success = True

            if filename:
                create_xml_files(xml_response, filename)

            # if not xml_response["response"]["result"]:
            #     print("Nothing found on PA/Panorama, are you connecting to the right device?")
            #     print(f"Check {filename} for XML API reply")
            #     sys.exit(0)

        elif xml_or_rest == "rest":

            response = self.get_rest_request_pa(restcall=xpath_or_restcall)
            json_response = json.loads(response)
            if json_response["@status"] == "success":
                success = True
            if filename:
                create_json_files(json_response, filename)

            # if not json_response["result"]:
            #     print("Nothing found on PA/Panorama, are you connecting to the right device?")
            #     print(f"Check {filename} for XML API reply")

        if not success:
            # Extra logging when debugging
            if DEBUG:
                print(f"\nGET request sent: xpath={xpath_or_restcall}.\n")
                print(f"\nResponse: \n{response}")
                create_xml_files(response, filename)
                print(f"Output also written to {filename}")
            else:
                print(f"\nError exporting '{filename}' object.")
                print(
                    "(Normally this just means no object found, set DEBUG=True if needed)"
                )

        if xml_or_rest == "xml":
            return xml_response["response"]
        else:
            return json_response
