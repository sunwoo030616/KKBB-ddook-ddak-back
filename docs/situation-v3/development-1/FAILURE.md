# Preflight only; zero external API requests
The test URL for the new planner was not updated alongside its temporary proxy endpoint. Mock tests failed before local model/backend startup and before any external API request. The runner now patches the corresponding mock URL too. The original local test failure is preserved.

Before any external call, catalog review also identified that the refund menu specifically requires open banking. Two not-yet-evaluated holdout queries were clarified to say open banking; IDs and intended outcomes did not change. Original preflight labels are retained in ../holdout-preflight-original.json. All subsequent actual development and evaluation use the new freeze; no provider results were consulted for this clarification.
