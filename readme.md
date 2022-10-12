Palo Alto Panorama Object Deduper
===========
Tool to check objects (addresses, address-groups, services, service-groups) across all Device Groups
and move duplicates into a (pre-existing) parent device group.

This is for a Palo Alto Panorama deployment.

**Now with 'secduper'!!**

Check for security rules that have the same destination (address/group, service & application). Add the
source address/groups from these rules to the first found duplicate, move over any extra tags not already
on the first rule, and delete the extra/duplicate rule. Somewhat still in progress/single use case. No changes
to Panorama are actually made, it outputs the necessary set commands only. Use DEVICE_GROUPS in settings.py to 
limit which groups are actually searched, if desired. No other variables in settings.py will have any affect.


## Notes
Death to 'shared'!! Use your own 'parent' device group instead.

- Currently tested on Panorama 10.1+ only, no plans on supporting anything below 10.1.
- If for some reason you want objects created in two 'parents', just put as many 'new parents' as you need
  in the list at settings.py 
- Minimum duplicates can be set to 1, we match on DUPLICATES, not objects.
- Will only look at and/or delete from 'shared' if we've already determined (on this run) the duplicates
  and just moved them to the new parent device group. If you've previously cleaned everything up and NOW want
  to remove from shared, you missed your chance! (This will be added soon though.)
- If tags exist on these objects, the tags will also be moved up to the parent device group. The first
  device group with the tag will be cloned/moved, any other device groups with the same tag name will take on
  the 'color' of this new tag.
- As usual when making major changes, get a Panorama named snapshot BEFORE pushing any changes. Sometimes it 
  can also be helpful to use this snapshot to check out the value of objects as they existed before the 
  changes were pushed, if errors occurred however you don't want to completely revert.
- Error codes/details found [here!](./errors.md)




#### Some notes on device group hierarchy 

```commandline
All-Devices
 EU
  site1
  site2
 NA
  site3
  site4
  West
   west1
   west2
  East
   east1
   east2
```
Taken the above hierarchy:
* If 'east1', 'east2', 'west1' and 'west2' all have the same object, but the objects only exist due to them being in
both 'West' and 'East' parent DG's (and not overridden), only 1 duplicate will be found, between 'East' and 'West' DG's.

* If all sites under 'NA' have the same object and do not override it, this is not a duplicate.
  - If you WANT the object/duplicate moved from 'NA' to 'All-Devices', put 'NA' in CLEANUP_DGS.

* All overrides are treated as a new/local object to whichever DG they belong, and will be deduped/listed out.


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

shared blah\
deep default, other deep?\
move from shared to parent dg---separate command, not dupe specific?\
make httpx timeout even longer?(and on httpx.client)\


