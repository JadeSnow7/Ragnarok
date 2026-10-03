# Handoff UX contract

## Business context
Source: the current requested local GOSIM proof, recorded in README.md and implemented by app.py and live_executor.py. Fixed mode does not contact a remote service. Explicit live mode uses the existing Codex login to send one fixture source and task, within the current user authorization. Runtime scope is trusted example code only; README.md owns limitations and lifecycle rules.

## Canonical UI Map
| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Form | web/app.js task form | README.md and app.py create validation | Task create only | tests/browser_smoke.py |
| Scrollbar | web/style.css root baseline | DESIGN.md | Geometry only | static CSS and browser smoke |
| Toast | web/app.js notice() live region | This contract | Pending/error/info | browser smoke |
| CRUD | app.py Handoff create/get/decide and web/app.js render | README.md lifecycle | Create/read/approve/reject; no delete | tests/test_runner.py |

No select, calendar, table selection, search, billing, account permissions, or external deletion is present.

## Flow ledger
Fixed create → awaiting approval → read current plan + patch → approve or reject. Approved task → running → passed or failed. Live create → generating → awaiting approval. Cancel → cancelling → cancelled only after confirmed process exit. Restart leaves unknown and blocks the execution slot. Rejected, failed, interrupted and passed are terminal. A retry needs a new task; idempotent retry of the same HTTP call never reruns execution.

Create and decisions stay on the task detail view, deep-linked by ?task=. New task creation is explicit. The server binds approval to revision and digest. Source: app.py Handoff lifecycle, tests/test_runner.py.

Evidence links (original fixture, fixed preview, and JSON evidence) navigate in the current browsing context without requesting a new window or tab. The source-informed integration expectation is that Rinx native Back returns through navigation history and Reload returns to the original mini-app launch URL; task-specific restoration requires launching with `?task=`. These Back/Reload expectations and the updated same-context links have not been verified in Rinx WKWebView. The recorded Mac browser checks predate this navigation change; they are not a UI rerun of the current source.

## Form and interaction state
The form uses explicit validation (novalidate), a labeled textarea, inline error, aria-invalid, aria-describedby and first-error focus. Draft text remains in sessionStorage. It has no privacy-sensitive inputs. Enabled controls have hover, active, focus; duplicate in-flight submits are disabled. Changes to task text do not expand the single supported recipe; the UI states that limitation before creation.

## Recovery and evidence
Timeouts do not mean execution failed. Preserve idempotency keys and allow retry of the same action. Polling recovers on transient failures. Raw service errors are rendered as text, never HTML. Keep approval, failure and result inline. Evidence contains UTC timestamps and actual command output. Do not run shell commands from task input.

## Locale and accessibility
Simplified Chinese UI with exact technical command identifiers in English. Native buttons, links, details and forms; keyboard focus visible; no modal, composite widget or native alert/prompt/confirm. One natural scroller and narrow-width reflow. Reduced motion is respected. Target WCAG 2.2 AA; complete browser/assistive-technology compliance is not claimed without running checks.

## Live mode extension (2026-10-03)
Native radio inputs choose fixed/live; no custom select. Existing render(), notice(), evidence details and inline approval remain canonical owners. Live mode is disabled until health confirms explicit enablement; availability is not proof of a successful model call. Diff, candidate/base/plan hashes and exact commands precede approval. Generation may run before approval, but target application and tests cannot. Model calls and target commands appear separately in evidence. Source: live_executor.py and tests/test_live.py.

Cancellation is an idempotent server request and does not immediately claim exit. Unknown state stays visible with a blocked slot. Terminal failures never use a passed preview. Normal temporary execution approval resolved the initial outer-sandbox socket restriction. Full HTTP tests and the fixed browser workflow passed; the real live review was checked on desktop and 390px with zero target execution. The exact real candidate was subsequently approved by the human, applied once, and passed the unchanged test suite plus browser reload checks; duplicate approval caused no new execution. No new Rinx claims.
