Panorama Object Deduper
===========
Tool to check objects (addresses, address-groups, services, service-groups) across all Device Groups
and move duplicates into a (pre-existing) parent device group.

## Notes
Death to 'shared'!! Use your own 'parent' device group instead.

We will grab the current parent device groups (if any) in case you already have a hierarchy
If you have a multi-tiered hierarchy already, it's probably best to customize your 'runs' to
only include the specific device groups and parent group you care about. 

If for some reason you want objects 
created in two 'parents', just put as many 'new parents' as you need in the list at settings.py

Minimum duplicates can be set to 1, we match on DUPLICATES, not objects.

Currently only looking at and/or deleting from 'shared' if we already determined it's a duplicate and are moving it
to the new parent device group.

## Installation
To install run:
(substitute python/pip with python3/pip3 if required on your system)

- `python -m venv myenv` <-- you should always create a virtual environment
- `source myenv/bin/activate` <-- and activate it
- `python -m pip install git+https://github.com/glspi/pan-deduper.git`

A 'settings.py' file is used for 'settings' (shocking huh?)
just run 'deduper' and it will be automatically created for you. Review the existing
settings and tweak as needed.

## Usage
To use:
`deduper --help`

#### Examples:
Connect to Panorama:

`deduper panorama -i 10.10.1.1 -u admin -p admin`

Grab objects from .xml file:

`deduper xml -f filename.xml`

TODO:

break testing in many ways\
tests!!\
notes about ["@loc"] not in settings.exclude_device_groups---parent?\
make httpx timeout even longer?(and on httpx.client)\
logging on 'gets'