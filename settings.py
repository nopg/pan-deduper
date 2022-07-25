"""
Variables to be updated by end-user on each run
"""
push_to_pa = False  # Duh
device_groups = []  # Leave empty if searching ALL device groups
exclude_device_groups = ["global"]  # Leave empty if searching ALL device groups
parent_device_group = ["global"]  # Where should we move the duplicate objects?
minimum_duplicates = 3  # At least this many device groups must have object before considered a 'duplicate' to move objects
to_dedupe = [
    "addresses",
    "address-groups",
    "services",
    "service-groups",
]
