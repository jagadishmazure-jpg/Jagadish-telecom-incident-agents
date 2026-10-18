"""Print correlation + dispatch on seeded data (rendered into README, checked in CI)."""
from telcoops import demo_helpers
from telcoops.correlate import correlate_alarms

print(demo_helpers.demo_correlation())
d = demo_helpers.demo_dispatch()
print(d["tech_id"], d.get("explanation", ""))
base = {"site_id": "SITE-NORTH", "severity": "major"}
for first, second in (("FIBER-CUT", "LINK-DOWN"), ("LINK-DOWN", "FIBER-CUT")):
    alarms = [dict(base, alarm_id="A1", raised_min=0, element_id="RTR-1", cause_code=first),
              dict(base, alarm_id="A2", raised_min=3, element_id="OLT-9", cause_code=second)]
    groups = correlate_alarms(alarms)
    print(f"{first} then {second}: {len(groups)} group(s): {groups[0].explanation}")
