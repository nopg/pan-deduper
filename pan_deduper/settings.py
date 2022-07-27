"""
Variables to be updated by end-user on each run
"""
push_to_panorama = True  # Duh
device_groups = []  # Leave empty if searching ALL device groups
exclude_device_groups = ["All-Devices"]  # Leave empty if searching ALL device groups
parent_device_group = ["All-Devices"]  # Where should we move the duplicate objects?
minimum_duplicates = 5  # At least this many device groups must have object before considered a 'duplicate' to move objects
to_dedupe = [
    "address-groups",
    "addresses",
    "service-groups",
    "services",
]  # List of objects to search through (Available: "addresses", "address-groups", "services", "service-groups")
