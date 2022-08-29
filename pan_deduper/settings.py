"""
Variables to be updated by end-user on each run
"""
PUSH_TO_PANORAMA = False  # Duh
DELETE_SHARED_OBJECTS = (
    True  # Search through shared and delete duplicates that might also exist in shared?
)
NEW_PARENT_DEVICE_GROUP = ["All-Devices"]  # Where should we move the duplicate objects?
DEVICE_GROUPS = []  # Leave empty if searching ALL device groups
EXCLUDE_DEVICE_GROUPS = []  # Leave empty if searching ALL device groups
#
MINIMUM_DUPLICATES = (
    5  # At least this many DUPLICATES before considered a 'duplicate' [1-999]
)
TO_DEDUPE = [
    "address-groups",
    "addresses",
    "service-groups",
    "services",
]  # List of objects to search through (Available: "addresses", "address-groups", "services", "service-groups")
CLEANUP_DGS = (
    []
)  # If you already have a parent, but want to move objects into a new parent device group
MAX_CONCURRENT = 200  # Maximum concurrent api requests to Panorama (lower if you are getting 'Internal Errors'
