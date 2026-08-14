# BibleGym

BibleGym is a GymAct-compatible bounded executable world for church formation and operations. It turns the church-engagement paper and prior church/Bible workflows into testable capabilities rather than a generic content app.

## Architecture

`public semantic graph -> ggen pack -> generated capability catalog -> BibleGymProvider -> GymAct authority gate -> actuation -> verification -> receipt/replay`

GymAct remains the execution/evidence boundary. BibleGym does not plan, preach, infer doctrine, send messages, move money, or replace pastoral/professional judgment. External planners/LLMs may construct candidate devotion text or plans from READ packets, but they receive no ambient DO authority.

## Implemented domain surface

- Global church tenancy: church/campus identity, BCP47-like locale, IANA timezone, currency and local Bible translation preference.
- One-tap profile, RSVP, attendance/volunteer check-in; QR event check-in; optional consent-gated geofence check-in.
- Next Steps, intent-only messaging/contact shortcuts, offline content-sync manifests, client-encrypted note references, and platform biometric assertions without biometric material.
- Guardian child check-in with pickup-secret hashing; no raw pickup secret persistence.
- Groups, accountability, events, sharing intents, reminders and offline content metadata.
- Welcome-team lifecycle from an empty roster: recruit -> onboard -> assign/co-chair -> check-in, with opt-out, notification stop, no-show gap creation, staffing-health inspection and governance escalation.
- Need-to-follow-up `ServiceRoute` records: need -> route -> door -> role -> assignment -> evidence -> receipt -> follow-up.
- Privacy-minimized prayer requests, Bible-need routing and follow-up; hosted autonomous groups explicitly preserve group governance while the church remains facility host, not owner.
- Giving *intent* only; no payment credentials or transaction actuation.
- Sermon -> scripture-linked quest -> two-minute/habit-stack practice -> completion -> milestones/badges/opt-in leaderboard.
- Scripture quiz and deterministic devotion prompt packets for external SELECT/CONSTRUCT systems.
- Friday Night Fellowship formation rail: Admit -> Believe -> Surrender -> Practice, bounded metadata only, next-faithful-action receipts, consent before feedback, and privacy-minimized care routing.

## Safety/privacy fences

BibleGym refuses raw confession/detail fields, precise-location persistence, payment-instrument storage, non-consensual accountability links, and detailed care-handoff narratives. Location check-in requires prior person consent plus a boolean geofence verdict. `record_care_handoff` records only category/reason/status. These are executable refusal paths, not documentation-only policy.

## Verification

```bash
python -m unittest discover -s tests -v
```

The tests execute the provider lifecycle, paper feature paths, privacy/safety refusals, global configuration, checkpoint/restore, and ontology/generated-catalog parity. When the real `gymact` package is installed, `biblegym.compat` uses its canonical `Capability` and `Consequence` classes directly; otherwise the same protocol surface is locally executable with a tiny compatibility type.

### Standing

Local direct provider lifecycle: `ALIVE` when the test suite passes. Real GymAct-kernel execution and real `ggen sync/receipt verify` require those toolchains and must be reported separately; their absence does not get promoted to success.
