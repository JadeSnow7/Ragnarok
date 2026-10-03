---
version: alpha
name: Handoff
description: "An inspectable engineering workbench with explicit approval and evidence"
colors:
  primary: "#225ad6"
  ink: "#152e45"
  muted: "#50647a"
  paper: "#f2f6fb"
  white: "#ffffff"
  line: "#d7e1ed"
  green: "#17674c"
  red: "#a72f31"
typography:
  sans:
    fontFamily: "Noto Sans CJK SC, Open Sans, system-ui, sans-serif"
  display:
    fontFamily: "DejaVu Sans, sans-serif"
  mono:
    fontFamily: "DejaVu Sans Mono, monospace"
rounded:
  DEFAULT: "12px"
  control: "7px"
spacing:
  section-gap: "24px"
  page-max: "1300px"
components:
  button: {}
  panel: {}
  status: {}
---
# Handoff design

## Overview
A small, inspectable engineering workbench for a GOSIM proof. The subject is a task being handed from a person to a bounded executor, with evidence returned. Audience: Chinese-speaking product/engineering collaborators, using desktop with a phone-width fallback. This is a product tool, not a marketing site. No Japan-market inference is made.

The signature is the evidence chain: a red expected baseline failure leads to green verified success; every step exposes command output. Anti-references: a chat clone, unearned progress percentages, sci-fi agent dashboards, or claims of autonomous work that did not happen.

Runtime CSS in web/style.css is canonical (Model B). The frontmatter mirrors its named semantic tokens; elements consume CSS variables. No generated theme adapter exists. The isolated Todo fixture is deliberately separate test content, not a sibling product screen.

## Colors
Blue is for actions and focus. Ink and muted text sit on white/pale-blue surfaces. Red indicates real errors or the specifically labeled expected baseline failure. Green is reserved for observed verification success. Amber is for pending approval. The product is light-theme-only; system forced-colors remains operable.

## Typography
Chinese-capable system stacks avoid font downloads. Display type is restrained to the main heading; compact monospaced command and hash values wrap rather than clip. Technical vocabulary remains English where it denotes exact executable names. Main controls and guidance use Simplified Chinese.

## Layout
A two-column task/review workbench at desktop widths; one natural-height column below 860px. Controls stay reachable at 390px, and the document owns page scrolling. Async feedback has reserved space. The process numbers are real ordered stages, not decoration.

## Elevation & Depth
Flat panels use borders and tone, never floating decorative shadows. Approval is an inline amber region, not a modal.

## Shapes
12px panels and 7px controls make content blocks and actions distinct. Pill-like status badges always contain text.

## Components
Canonical owners are recorded in UX-CONTRACT.md. Primary and secondary buttons share hover, active, focus, disabled and busy behavior. One notice live region owns async feedback; critical results remain inline. Error and helper text reserve room and associate with the textarea.

The text-based evidence icon always has an adjacent name and exit code. No icon-only action exists. Motion is limited to 140ms button feedback and disabled under reduced motion. No fake streaming, simulated logs or random progress. Root-level scrollbar tokens apply to every owned overflow region, with standards and WebKit fallback rules.

Token mapping: colors.primary→--blue; colors.ink→--ink; colors.muted→--muted; colors.paper→--paper; colors.white→--white; colors.line→--line; colors.green→--green; colors.red→--red; typography.sans→--font-body; typography.display→--font-display; typography.mono→--font-mono; rounded.DEFAULT→--radius; spacing.section-gap→--space. Controls consume these values in web/style.css.

## Do's and Don'ts
- Do expose patch, scope, real commands, exit codes, and known limitations
- Do require an explicit reviewed-plan decision before target application or tests
- Don't imply that directory copying is an OS sandbox or that fixed patch replay is autonomous model execution
- Don't hide failed or unrun verification behind a green global result

Live mode extends the existing evidence chain with explicit generation, cancellation and unknown states. Native radio controls use the existing semantic tokens; no new visual system. Model execution and fixed replay always carry distinct text labels.
