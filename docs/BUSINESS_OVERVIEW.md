# Conditia — Business Overview

**Product:** Conditia (`conditia.ai`)
**Category:** Asset-condition intelligence for fleets
**Stage:** MVP — trucking vertical first

---

## 1. What Conditia is

Conditia is a **system of record for the physical condition of fleet assets**. A
driver or yard worker walks around a truck with their phone, follows a guided
capture flow, and uploads the footage. Conditia stores that capture, analyzes it
for damage, and presents fleet managers with a dashboard showing each asset's
condition, a visual damage map, and — most importantly — **how that condition
has changed over time**.

In one sentence: **phone capture in → timestamped, legible condition report and
change history out.**

The product is deliberately *hardware-agnostic*. Mobile phone capture is the
MVP, but the architecture treats the capture source as a single recorded
attribute, so drones and fixed yard cameras can feed the exact same analysis
pipeline later without redesign.

---

## 2. The problem we solve

Fleets (trucking first) constantly move high-value assets between drivers,
yards, customers, and repair shops. Today, the condition of those assets is
tracked with:

- paper or PDF walk-around checklists,
- loose phone photos with no structure or history,
- and human memory.

This creates expensive, recurring pain:

- **Liability disputes.** When a truck or trailer comes back damaged, nobody can
  prove *when* the damage happened or *who* had custody. That ambiguity costs
  money in write-offs, chargebacks, and customer disputes.
- **Missed early damage.** Small cracks, rust, and tire wear go unnoticed until
  they become safety issues, roadside failures, or failed DOT inspections.
- **No condition timeline.** A photo from today is nearly useless without the
  photo from last month to compare it against. Existing tools capture images but
  don't answer "is this new?"
- **Inconsistent inspections.** Quality depends on which driver did the
  walk-around and how thorough they felt that day.

## 3. Why now / why this is hard to do well

The differentiator is **change over time**, not damage detection in isolation.
Lots of tools can take a photo. The valuable, defensible question is: *"Was this
dent here last week, or did it appear during this trip?"* Answering that
reliably requires a structured capture process, a consistent per-asset history,
and damage findings that can be matched across inspections. That is the core of
what Conditia builds.

---

## 4. Who it's for

Conditia serves **two distinct audiences sharing one system of record**:

| Audience | Where / how | What they need |
|----------|-------------|----------------|
| **Fleet managers / operations** | Desktop, in an office, daytime | Scan fleet health at a glance, drill into a truck's damage map, review findings and severity, export reports, settle liability questions. Data-dense but scannable. |
| **Drivers / yard staff** | Phone, outdoors, often gloved, bright sun or dusk | A dead-simple guided walk-around. Capture the right angles, upload, done. No interpretation required from them. |

The manager is the buyer and primary daily user; the driver is the data-capture
front line whose experience must be frictionless or the data never gets
collected.

---

## 5. How it works (business-level flow)

1. **Register the asset.** A truck/trailer is added to the fleet (VIN, plate,
   make/model/year).
2. **Guided capture.** A driver opens the capture flow on their phone and is
   guided through the required angles (front, rear, driver side, passenger side,
   etc.).
3. **Upload.** The captured photos/video are uploaded against that inspection.
4. **Analysis.** Conditia processes the media, identifies potential damage
   findings, and — critically — checks each finding against the asset's prior
   inspections to determine whether it is **new** or **previously seen**.
5. **Report & dashboard.** The fleet manager sees KPIs, a list of recent
   inspections, a per-truck damage map with severity-colored zones, and findings
   annotated with "first detected / previously detected."

A core trust principle: **Conditia never reports an un-analyzed inspection as
"clear."** If the system cannot confidently analyze the footage, the inspection
is flagged for **human review** rather than silently passed. The product's value
is its credibility as a system of record, so it errs toward honesty over false
reassurance.

---

## 6. Value proposition

- **Settle liability with evidence.** Timestamped, per-asset condition history
  turns "he said / she said" into a defensible record of when damage appeared.
- **Catch damage earlier.** Consistent, structured inspections surface rust,
  cracks, and wear before they become roadside failures or compliance problems.
- **Standardize inspection quality.** A guided flow makes every walk-around
  consistent regardless of who performs it.
- **Change-over-time intelligence.** The headline differentiator: not just "is
  it damaged," but "did this change since last time, and when did it start."

---

## 7. Brand & positioning

Conditia's authority comes from being **accurate, timestamped, and legible** —
it is an *instrument*, not a flashy app. The brand personality is **precise,
dependable, calm.** The interface is a light, clean fleet-operations console in
the spirit of Samsara / Motive, but with its own identity. Color is used almost
exclusively to convey **severity** (Critical = red, Medium = amber, Low = blue,
Clear = green), never as decoration. "The data is the hero."

Positioning line: *hardware-agnostic asset condition intelligence — starting
with trucking.*

---

## 8. Market & expansion path

- **Beachhead:** trucking fleets (trucks and trailers), where custody changes
  hands constantly and liability disputes are frequent and expensive.
- **Adjacent expansion (same product, new capture source):** any operation that
  needs to track the physical condition of high-value movable assets over time —
  e.g. equipment rental, construction machinery, rail, aviation ground
  equipment, and shipping containers.
- **Capture-source expansion:** because the platform is hardware-agnostic, drone
  and fixed-camera capture can be added to serve yards and depots at scale
  without rebuilding the analysis pipeline.

---

## 9. Current status (honest assessment)

Conditia is a **working MVP**, not yet a production multi-tenant SaaS. What works
today: guided mobile capture, structured upload, the inspection lifecycle, the
fleet dashboard with KPIs and a damage map, and change-over-time tracking across
an asset's history.

What is intentionally **not** production-ready yet:

- **Automated damage detection is not validated.** The detection model is a
  placeholder; experimental image-label detection exists but always routes to
  human review. A trained, calibrated damage model is a prerequisite before the
  automated findings can be trusted commercially.
- **Single-tenant security perimeter.** Access is currently a service-level API
  key scoped to one fleet — there is no per-user identity, roles, or audit log
  yet. Real multi-tenant customer accounts are future work.
- **Reporting/PDF export and some dashboard areas** are partially built.

These are deliberate, documented boundaries — the engineering posture is to be
truthful about what is and isn't ready rather than overstate capability, which
matches the product's whole premise of being a trustworthy system of record.

---

## 10. Roadmap themes (business priorities)

1. **Validated damage detection** — the single biggest unlock for commercial
   trust and automation.
2. **Multi-tenant accounts, identity, and roles** — turn the single-fleet
   perimeter into real customer organizations.
3. **Reports & exports** — shareable, defensible condition reports (PDF) for
   liability and compliance use.
4. **Additional capture sources** — drone and fixed-camera ingestion for yards.
5. **Integrations** — connect with existing fleet/telematics systems so Conditia
   fits into operators' current workflows.
