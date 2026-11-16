# Local result parser failure after 3 real requests

The adapted runner used the prior provider-name branch when extracting selected menus. All three real hybrid responses were treated as if they were the old full-catalog GPT response and caused local KeyError. The runner stopped after three failures. Provider usage and raw planner/JEV answers are preserved. These rows remain errors in this run; they are not silently repaired or merged into final scores.

The parser now reads the actual hybrid `menus` array and retains the entire local API response before interpretation. The inference implementation is unchanged. These three requests count against the development budget.
