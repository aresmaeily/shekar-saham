# D-O1 APPROVAL PACKAGE — R2 REVIEW PROCEDURE v0.2 — 2026-10-23 — READY_FOR_OWNER_DECISION

Purpose: the concise, complete approval package for decision **D-O1**
(required by CONSOL-GOV-14 §4.7). One owner message closes this decision.

## 1. Requested decision (exact)

The owner records ONE of:

- **APPROVE**: "D-O1: I approve the G2 review procedure v0.2, version
  identifier `G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md`,
  SHA-256 `0045febaa59a7baae0baf093c0bb6525b1a5ba138f648eed9b88a9b2cc65dafc`."
  (Optionally also transcribe the four approval-block fields directly into
  the file — or authorize verbatim transcription; the block is owner-only.)
- **AMEND-THEN-APPROVE**: name the clause(s) and required change; the
  implementing side prepares a v0.3 diff for re-approval.
- **REJECT**: with a reason; the procedure question returns to the owner
  with a fresh proposal.

Absence of response is not approval. Self-approval is void.

## 2. Selected candidate — identity

- File: `docs/active/G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md`
- Full SHA-256: `0045febaa59a7baae0baf093c0bb6525b1a5ba138f648eed9b88a9b2cc65dafc`
- Size/lines: 12,328 bytes / 214 lines (re-verified 2026-10-23)
- Git status: tracked, clean
- Approval block: EMPTY (all four fields underscores; verified fresh and
  enforced by a regression test `test_real_v02_file_block_is_empty`)
- Provenance: consolidation of v0.1 + six dated addenda at commit
  `c661a617b9f3fba2b70c1ea232f19f389115c8ce` (GOV-10), prepared under
  GOV-12 Block D.7; clause-by-clause traceability R1–R23 executed under
  GOV-13 §4 (0 contradictions / 0 new requirements / 2 cosmetic
  compressions / 0 defects requiring repair).

## 3. Why v0.2 (and why the alternatives are rejected or superseded)

1. **v0.1 + six addenda** — the semantic source; NOT selected for approval
   because a 7-document append-only chain cannot be approved in one act
   and carries cross-references that have already required status-schema
   correction (GOV-10). They remain UNTOUCHED canonical history and govern
   over v0.2 in case of any divergence (v0.2 precedence clause).
2. **GOV-11 reviewer-sandbox scaffold** — never existed in this primary
   environment; non-canonical; not a candidate.
3. **Any new consolidation** — unnecessary: R1–R23 found zero defects
   requiring repair in v0.2; a v0.3 would change the hash the owner has
   already seen reported across two cycles without semantic benefit.

## 4. Material differences v0.2 vs v0.1 + addenda (complete list)

Eight recorded consolidation items (v0.2 §Change summary): GOV-6 #1/#2/#3/
#4/#5/#6 incorporations (exception form, COI form, re-review thresholds,
sign-off block, E1–E6 substitution tightening, verdict-rule codification);
GOV-8 battery-currency note; GOV-10 Annex A status schema + explicit
precedence rule + decision-separation clause. Two cosmetic compressions
(T1 inline quote/filename; T2 illustrative parentheticals) — non-semantic,
recorded GOV-13 §4.

## 5. Unresolved risks (complete)

- None technical. The procedure is a review-governance document; it
  confers no runtime capability and changes no gate by itself.
- Process risk: approval of the procedure does NOT appoint anyone and does
  NOT schedule anything (D-O2, R-A1, R-A2, D-O3, D-O4 remain separate).
- If the owner amends (option AMEND-THEN-APPROVE), the hash changes and
  this package must be re-issued for the new hash.

## 6. Consequences of approval (exact, no overclaim)

- The procedure versions to **v1.0** and becomes the operative G2 review
  procedure (v0.2 §Provenance/§Approval block).
- The chain D-O2 (appointment) → R-A1/R-A2 (acknowledgement + COI) →
  D-O3/D-O4 (adjudication + scheduling) → convened review at a fixed SHA
  → owner verdict (T6) becomes EXECUTABLE.
- **E5 can then be satisfied** — but only by the reviewer's written
  acknowledgement, never by the implementing side.
- G2 itself remains NOT_PASSED until the owner records the verdict after
  a real review. Nothing is auto-passed by this approval.

## 7. Decision record locus

The owner's message text (verbatim) will be appended to the CONSOL-GOV-14
cycle record and the approval block transcribed only under explicit
transcription authorization; the decision register row will cite the full
hash above.
