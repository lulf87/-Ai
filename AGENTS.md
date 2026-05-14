# AGENTS.md

## Project-Specific Rules

These rules apply to this repository and override broader defaults when they are more specific.

## Browser Verification Is Required

After every program update, run a real browser verification before reporting the work as complete.

This applies to changes in:

- frontend UI or styling
- backend APIs
- document upload, extraction, rule checking, reporting, or regulation workflows
- sample-data flows that affect the demo experience

Minimum browser verification after an update:

1. Start or refresh the backend and frontend local servers.
2. Open the app in a real browser at the local dev URL.
3. Exercise the affected user flow through the UI, not only by API calls.
4. Check the browser console for errors.
5. Report the exact browser scenario tested and whether it passed.

For this V0.2 demo, the default full-flow browser test is:

1. Create a new project.
2. Upload the golden sample documents from `samples/golden/microwave_ablation/`.
3. Extract product master data and run AI extraction.
4. Run rules and AI risk analysis.
5. Confirm at least 14 rule findings are shown plus AI candidate findings.
6. Confirm at least one AI candidate and reject at least one AI candidate.
7. Generate a Word report and confirm the download link appears.
8. Confirm there are no unexpected browser console errors.

Automated tests and builds are still required where meaningful, but they do not replace browser verification.

## Evidence And Safety

- Do not edit raw customer input files in place.
- Treat uploaded registration materials as read-only.
- Do not claim a regulatory conclusion unless it is traceable to evidence or explicitly marked as pending confirmation.
- Do not use unverified regulations as final rule basis.
