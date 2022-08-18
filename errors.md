Error Codes
===========
More details on error messages you might see in deduper.log

## Tips
- If using grep, add `-A 1` to your command to include the line following the captured grep output
  (most errors will be 2 lines)
  - (ie. `grep 'Failed' -A 1 deduper.log`)

## Messages
- Object Not Unique &emsp; - &emsp; Object already exists in this device group. 
  - If device group is the Parent DG, this can likely be ignored. Possibly add Parent DG to the Excluded DG's
    in settings.py?
- Name Not Unique &emsp; - &emsp; See above
- Reference Not Zero &emsp; - &emsp; Object still in use elsewhere so cannot delete
  - This can sometimes be caused by the new object in the Parent DG failing to be created.
- Invalid Object &emsp; - &emsp; Panorama didn't like what we sent, likely a bug.
- Internal Error &emsp; - &emsp; Panorama failed to process the request.