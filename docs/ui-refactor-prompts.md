# UI Refactor Prompt Set

## Online Reference Summary

This UI should behave like a focused compliance workbench rather than a marketing site. The most relevant references are:

- Ant Design data display guidance: prioritize information by importance, operation frequency, and relationship; use tables/lists for dense comparison.
  https://ant.design/docs/spec/data-display/
- Ant Design data list guidance: lists should be easy to scan and help users quickly find objects.
  https://ant.design/docs/spec/data-list/
- Carbon dashboard guidance: establish a strong hierarchy, limit nonessential metrics, keep color assignments consistent, and use spacing to clarify priority.
  https://carbondesignsystem.com/data-visualization/dashboards/
- Drata compliance dashboard/product references: compliance tools need readiness summaries, alerts, tasks, owners, and evidence status close to the main workflow.
  https://help.drata.com/en/articles/7963882-operational-compliance-dashboard
  https://drata.com/products/compliance/controls-and-evidence
- Sprinto dashboard references: compliance work benefits from a central dashboard for posture, pending work, risks, audits, evidence, and streamlined navigation.
  https://docs.sprinto.com/dashboard/overview

## Master Prompt

Refactor this registration-material AI review demo into a dense enterprise compliance workbench for Chinese medical device registration teams. Preserve all current business functions and safety boundaries. Do not turn it into a landing page. The first screen must expose project state, document readiness, extracted master data progress, risk findings, verified regulation evidence, and report readiness. Use a restrained professional palette with neutral surfaces plus semantic risk colors. Prefer compact status chips, metric tiles, workflow steps, evidence blocks, and scan-friendly lists. Keep controls close to the task they affect.

## Information Architecture Prompt

Reorganize the UI around the reviewer workflow:

1. Project setup and switching in a persistent left sidebar.
2. Command center at the top with 4 to 6 metrics: uploaded materials, required gaps, rule findings, AI candidates, verified regulations, report state.
3. Workflow rail showing the review sequence: create project, upload documents, extract master data, run rules/AI review, verify findings, generate report.
4. Main work sections in descending operational priority: documents and regulation sources, checklist, master data, risk findings, report output.
5. Every AI or regulation-derived result must be visibly marked as pending, confirmed, rejected, or verified.

## Visual System Prompt

Design a quiet enterprise SaaS interface for repeated daily use. Use compact typography, 8px spacing rhythm, cards only for repeated records or framed tools, and clear table/list rows. Avoid oversized hero blocks, decorative gradients, bokeh/orbs, stock imagery, and one-note color themes. Use semantic colors consistently: red for high risk, amber for attention, green for ready/verified, blue for AI/regulatory assistance, neutral gray for pending. Ensure Chinese labels do not wrap awkwardly inside buttons or status chips.

## Component Prompt

Create reusable visual patterns without large architectural refactors:

- Sidebar brand block with project creation form and project switcher.
- Metric cards for counts and readiness.
- Step cards for workflow status.
- Compact action groups using lucide icons.
- Status chips for source type, review status, verification status, and risk level.
- Evidence panels with document evidence and regulation evidence visually separated.
- Empty states that state what is missing without implying regulatory conclusions.

## Verification Prompt

After the UI update, run the frontend build and verify the app in a real browser. Exercise the demo flow through the UI, including creating/selecting a project, loading golden sample documents, extracting master data, running rules, running AI risk analysis, confirming and rejecting at least one AI candidate when available, and generating a Word report. Check the browser console. Report exact scenarios tested, pass/fail status, and any unverified items.
