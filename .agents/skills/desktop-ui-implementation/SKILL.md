---
name: desktop-ui-implementation
description: Implement or refine a feature's desktop UI from its design reference and README specification.
---

# Desktop UI Implementation

Use when implementing or modifying a page or reusable desktop UI.

## Required inputs

- Target feature folder, for example `design/dashboard/`.
- Its `README.md`.
- Its reference image(s).
- Existing app layout and shared components.

## Workflow

1. Read the feature README and inspect every reference image.
2. Inspect the current routing, app shell, design tokens, and shared components.
3. Map each visible region in the reference to a component.
4. Identify every control and its specified action.
5. Implement the page using existing shared components first.
6. Add loading, empty, error, and success states.
7. Verify layout at the intended desktop size and ensure it remains usable when resized.
8. Test every interactive control.

## Implementation guidance

- Match hierarchy, spacing, alignment, typography, and density before adding decoration.
- Prefer conventional desktop patterns: sidebar, toolbar, breadcrumbs, tables, context menus, dialogs, and detail panels.
- Use consistent button variants and icon sizes.
- Use Lucide icons already available in the project.
- Do not invent interactions that are absent from the specification.
- If a control's behavior is unspecified, do not give it a misleading action; report the missing requirement.
- Do not put AI chat or AI branding into a page unless its feature specification requires it.

## Completion

Compare the implementation with the reference image and report visual differences, functional coverage, and tests performed.
