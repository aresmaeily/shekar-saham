# P5-MAP-01 Mapping Baseline Contract Verification

## STATUS

DESIGNED_ONLY

## PURPOSE

Define the scope and verification requirements for mapping baseline behavior without changing runtime implementation.

This work package is a NEW controlled specification. It is not a continuation of any prior "P5-WP-01" work. Repository audit at HEAD `c1984e7979f89f2d727b471deb602953ec62fad5` (branch `main`) found no P5-WP-01 artifacts in the working tree or in any commit on any ref; no such artifacts are recovered, recreated, or assumed by this document.

## SCOPE

Include only:

1. Symbol identity resolution behavior
   - How an input symbol reference is resolved to a single instrument identity.
   - Which identity attributes participate in resolution and in what precedence.
   - Behavior when no match, one match, or multiple matches exist.

2. Symbol normalization observation
   - Observation of the normalization currently applied to symbol inputs (character forms, whitespace, case, script variants) as the code exists today.
   - Recording of observed input/output pairs. No new normalization rules are defined by this document.

3. Duplicate selection deterministic rules
   - The rule set by which one candidate is selected when multiple candidates map to the same normalized symbol.
   - Requirement that the selection is deterministic: identical inputs and identical candidate sets produce the identical selection across repeated runs.
   - Tie-break ordering, and behavior when tie-break inputs are missing.

4. Provider identity fields behavior
   - Which provider-supplied fields are treated as identity fields.
   - How identity fields are carried through mapping unchanged versus transformed.
   - Behavior when identity fields are absent, empty, or conflict between providers.

5. Cache behavior contract observation
   - What is cached at the mapping layer, keyed by what, with what lifetime.
   - Whether a cache hit can return a different identity than a fresh resolution for the same input.
   - Invalidation and staleness behavior as currently implemented.

## OUT OF SCOPE

Explicitly exclude:

- backend/app changes
- provider changes
- API changes
- database changes
- architecture changes
- AI architecture changes
- production mutation
- new normalization rules

Any future work that requires an item in this list is a separate work package and must not be executed under P5-MAP-01.

## EVIDENCE REQUIREMENTS

Future verification must distinguish the following evidence classes. A claim may only be labeled with the class whose conditions it actually meets.

Observation:
- mock-based behavior observation
- Behavior recorded against stubbed, fixture, or mocked inputs and dependencies.
- Establishes what the code does under controlled inputs. Does not establish runtime or production behavior.

Verification:
- runtime execution evidence
- Behavior recorded from executing the actual application code path (for example, a test or script that exercises the real resolver, normalization, duplicate selection, and cache code) with captured command, output, exit code, and commit SHA.

Production proof:
- live environment evidence
- Behavior recorded from the deployed or target environment against live provider data, with captured environment identifier, timestamp, inputs, and outputs.

Each future evidence record must state: evidence class, command or procedure, raw output, exit status, repository HEAD SHA, and the date of capture. Evidence of one class must never be reported as a higher class.

## ACCEPTANCE CRITERIA

AC-01:
Mapping behavior scope documented.
Met when: the five in-scope areas and the exclusion list above are written and agreed. Status of AC-01 at this document's creation: DOCUMENTED (this document).

AC-02:
Identity fields requirements documented.
Met when: the set of provider identity fields, their pass-through or transformation rule, and absent/empty/conflict handling requirements are enumerated in a follow-on section or document, referencing the actual code paths by file and symbol name.

AC-03:
Normalization behavior requirements documented.
Met when: the currently applied normalization steps are listed as observed (not designed), with representative input/output pairs and the code location of each step.

AC-04:
Duplicate resolution requirements documented.
Met when: the deterministic selection rule and tie-break order are stated, together with the requirement and method for proving determinism across repeated runs.

AC-05:
Cache behavior verification requirements documented.
Met when: cache key composition, lifetime, invalidation triggers, and the hit-versus-fresh consistency requirement are stated, with the verification procedure needed to demonstrate each.

AC-02 through AC-05 are NOT met by this document. This document defines what those criteria require; it does not satisfy them.

## GOVERNANCE RULES

- Evidence > inference.
- Documentation is not implementation.
- Design is not execution.
- No PASS/READY/LIVE/PROVEN without evidence.
- Human remains final authority.

## CONTROLLED VOCABULARY FOR THIS WORK PACKAGE

STATUS: DESIGNED_ONLY
IMPLEMENTATION: NOT_EXECUTED
RUNTIME: NOT_EXECUTED
EVIDENCE: DOCUMENT_ONLY

## RECORD

- Created against repository HEAD: `c1984e7979f89f2d727b471deb602953ec62fad5`
- Branch: `main`
- Files changed by this work package: this document only.
- backend/app, backend/tests, providers, dependencies, and database: unchanged.
