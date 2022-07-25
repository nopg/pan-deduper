device_groups = []  # Leave empty if searching ALL device groups
exclude_device_groups = ["global"]  # Leave empty if searching ALL device groups
minimum_duplicates = 3  # At least this many 'duplicates' before considering to move objects
to_dedupe = ["addresses", "address-groups", "services", "service-groups"]#, "address-groups", "services", "service-groups"]