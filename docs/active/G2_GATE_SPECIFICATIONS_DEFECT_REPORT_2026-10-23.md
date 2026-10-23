# G2 GATE SPECIFICATION DEFECT REPORT — G1/G3/G4/G5 UNDEFINED — WITH NARROWEST AMENDMENT PROPOSAL — 2026-10-23

Status: **SPECIFICATION DEFECT REPORT + PROPOSAL — NOT AN AMENDMENT IN
FORCE.** The proposal below has no governing effect until the owner
ratifies it (the same authority class as every roadmap/gate definition:
`04:72` Role 1 A; `05:148-150`). Nothing here is invented into force.

## 1. Defect statement (CG13-04, formalized per CONSOL-GOV-14 §9.3–9.4)

The canonical amendment corpus defines **G2** only:

- `04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md:72` — RACI:
  "G2: 1(A), 6/14(R), 9/10/15(C)".
- `05_GOVERNANCE_DECISION_REGISTER_CURRENT_2026-10-02.md:102-107` —
  D-AI-26: "G2 remains the independent validation gate and blocks
  real-data AI-2…".
- `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md:7-11,32-37,200-204` — the
  dependency chain positions G2 between P3 and P4/P5/P6.
- `03_AI_GOVERNANCE_BOUNDARIES_CURRENT_2026-10-02.md:61-66` — G2 as an
  AI-2 prerequisite.

The identifiers **G1, G3, G4, G5 appear in no canonical source** — no
definition, no acceptance criteria, no owner, no evidence requirements.
They are nevertheless referenced operationally (state file, roadmap
discussions, prior directive language) as if they were gates. This is a
specification incompleteness, not an implementation defect: the
implementing side correctly refused to invent definitions (GOV-13 CG13-04)
and continues to refuse.

Precise defect class: **missing specification** for four referenced-but-
undefined gate identifiers; secondary defect class: **naming collision
risk** (any future canonical definition could conflict with informal
usage that has accumulated around these identifiers).

## 2. Impact

1. G2's own chain is fully specified and executable (v0.2 procedure
   pending D-O1) — the missing G1/G3/G4/G5 definitions do NOT block G2.
2. Any roadmap statement implying "all gates G1–G5" is currently
   unverifiable — the honest state is `NOT_DEFINED`, and no acceptance
   evidence can exist for an undefined predicate.
3. Risk of accidental authority expansion: without definitions, a future
   implementer could be tempted to define these gates themselves and
   self-close them. This report closes that path: only the owner may.

## 3. Narrowest amendment proposal (PROPOSAL — owner ratification required)

Option A (recommended — minimal, honest): **owner decision that G1, G3,
G4, G5 are NOT gates** in the current roadmap revision; the operational
sequence P0-C → P0-V → P1 → P2 → P3 → G2 → P4/P5/P6 → AI-1 → AI-2 →
AI-MA → AI-3 → AI-4 → AI-5 → AI-6 → AI-7 (02:5-8) contains exactly one
named gate (G2) plus the P3.43 launch gate and the AI-stage evidence
gates (D-AI-26/29/30/31, D-AI-28/40). Under Option A the identifiers G1,
G3, G4, G5 are recorded as historical artifacts with no current force,
and the state file records `NOT_DEFINED — no canonical definition; not
gates per owner decision <ref>`.

Option B (only if the owner actually intends four additional gates): the
owner supplies, for each of G1/G3/G4/G5: name, scope, precise acceptance
criteria, required evidence, owning authority (A/R/C per 04:72 RACI
form), invalidation conditions, and dependency position in the 02:5-8
chain. The implementing side will then integrate them exactly like any
owner-supplied amendment (import + verification + test/battery impact
analysis). The implementing side will NOT draft these definitions
itself, because gate definitions are authority-bearing owner content.

Recommendation: **Option A** — it requires one owner sentence, removes
the collision risk, and matches the observable fact that the roadmap
chain is fully ordered without them.

## 4. Traceability

- Defect first recorded: GOV-13 §7 (CG13-04) — "G1/G3/G4/G5 recorded
  NOT_DEFINED in the canonical corpus (spec issue — not invented)".
- Directive basis for this report: CONSOL-GOV-14 §9.3–9.4 ("Explicitly
  identify missing or undefined criteria. In particular, do not invent
  G1/G3/G4/G5 definitions if they are absent from the authoritative
  material. If the specification is incomplete or contradictory, produce
  a precise specification defect report and the narrowest proposed
  amendment, with traceability to the existing decisions.").
- Search evidence: canonical corpus grep for `\bG[1-5]\b` shows G2-only
  definitions; the five canonical documents are byte-digest-pinned
  (corpus 7/7, harness G2-C-iv).

## 5. Disposition while unratified

State file and gate matrices continue to record
`G1/G3/G4/G5: NOT_DEFINED (spec issue; not invented; owner input
optional)` — exactly as GOV-13 recorded. No gate status may be derived
from an undefined identifier; no battery component may claim to test
them; the harness does not emit predicates for them.
