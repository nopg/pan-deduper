Panorama Object Deduper
===========
Tool to check objects (addresses, address-groups, services, service-groups) across all Device Groups
and move duplicates into a (pre-existing) parent device group.

## Installation
To install run:
`pip install git+https://github.com/glspi/pan-deduper.git`

## Usage
To use:
`deduper --help`

#### Examples:
Connect to Panorama:
`deduper panorama -i 10.10.1.1 -u admin -p admin`

Grab objects from .xml file:
`deduper xml -f filename.xml`

