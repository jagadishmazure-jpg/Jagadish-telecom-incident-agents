# SOP-02: Alarm correlation playbook

## 1. Suppress the storm
When more than ten alarms raise on one element inside fifteen minutes,
treat them as one correlated incident. Work the incident, not the alarms:
pick the highest-severity alarm as the lead and park the rest under it.

## 2. Find the common cause
Check cause-code affinity before dispatching: LINK-DOWN storms that follow
a fiber maintenance window are usually one cut, not twelve failures. The
correlation engine groups by element, site, cause affinity and time
window, and every group must carry its grouping explanation.

## 3. Re-correlate on change
If a new critical alarm raises on an element that already has an open
correlated group, attach it to the group instead of opening a new
incident. Split a group only when the field tech confirms two independent
faults.
