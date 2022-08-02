"""
Variables to be updated by end-user on each run
"""
PUSH_TO_PANORAMA = False  # Duh
DELETE_SHARED_OBJECTS = True  # Delete shared after cleanup/deduplicaton?
DEVICE_GROUPS = []  # Leave empty if searching ALL device groups
EXCLUDE_DEVICE_GROUPS = []  # Leave empty if searching ALL device groups
NEW_PARENT_DEVICE_GROUP = ["All-Devices"]  # Where should we move the duplicate objects?
MINIMUM_DUPLICATES = 5  # At least this many device groups must have object before considered a 'duplicate' to move objects
TO_DEDUPE = [
    "address-groups",
    "addresses",
    "service-groups",
    "services",
]  # List of objects to search through (Available: "addresses", "address-groups", "services", "service-groups")
