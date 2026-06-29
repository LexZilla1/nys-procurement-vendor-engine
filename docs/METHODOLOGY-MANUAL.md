# Golden Copy — Methodology Manual

**What this document is.** The operating manual for how the NYS Procurement Vendor golden copy is built,
verified, and kept current. The golden copy itself (see `golden-copy-INDEX.md` and the
`sources/` folder) is the *what* — the rules. This manual is the *how* — the standard every
rule is held to and the exact procedure used to get it there. It exists so the method is
auditable and repeatable by anyone, not just reconstructable from chat history.

**Status:** Phase 1 reference. Version 1.1, 2026-06-29. (v1.1 adds the load-bearing-passage method and
cross-authority discipline to §6, and §11 on the pain-point layer.)

---

## 1. Purpose and the liability model

The golden copy is a verified, primary-source rulebook of New York State procurement and
payment rules. The NYS Procurement Vendor SaaS validates vendor and not-for-profit (NFP) documents against
it. The product's trustworthiness rests entirely on the rulebook being correct, so the
rulebook is built to one standard: **nothing enters it that has not been verified, word for
word, against the official primary source.**

The reason this standard is non-negotiable is a liability argument, not a stylistic
preference:

- If the SaaS tells a vendor that an invoice must contain field X, and that instruction is
  NYS Procurement Vendor's paraphrase of the rule, then a wrongful rejection traceable to a wording error is
  NYS Procurement Vendor's fault.
- If the same instruction reproduces the State's own text verbatim — the exact words from the
  OSC Guide to Financial Operations (GFO) page or the State Finance Law section — then a
  rejection can never be blamed on NYS Procurement Vendor's wording. The vendor was told exactly what the
  State says.

Verbatim text is therefore a risk-transfer mechanism. It moves the authorship of every rule
back to the State, where it belongs. This is why paraphrase is prohibited even when a paraphrase
would read more smoothly.

---

## 2. The two definitions of "perfect"

The rulebook distinguishes two things that are easy to conflate. Holding them apart prevents
overpromising what the product can do.

1. **Rules are perfect.** Each rule is exact, sourced, dated, and free of paraphrase drift.
   This is fully achievable and is what the golden copy guarantees.
2. **A generated document passing is NOT something the rulebook alone can guarantee.** Every
   RFP or IFB adds solicitation-specific requirements that live only in that document, and a
   rejection can turn on vendor-supplied facts the rulebook cannot independently verify. The
   rulebook encodes the universal rules correctly; it cannot promise that any given submission
   clears every per-solicitation hurdle.

Practical consequence: rules flagged `Scope: Universal` are general. A per-solicitation layer
must always be read fresh from the actual RFP/IFB on top of them. The product validates against
the universal layer and surfaces — not silently resolves — the per-solicitation gaps.

---

## 3. The verbatim standard

Every rule is reproduced exactly as the State states it: every word, every comma, every list
marker, every internal quotation. The transcription preserves even apparent imperfections in
the source — see §7 on source quirks — because the goal is fidelity to the source, not a
cleaned-up version of it.

What "verbatim" forbids:

- Rewording, summarizing, or "tightening" the State's text.
- Silently correcting the State's typos, numbering gaps, or formatting.
- Merging two provisions into one statement of the rule.
- Dropping qualifiers ("if applicable," "to the extent practicable," "may" vs. "must").

What "verbatim" permits, because it does not change meaning:

- Normalizing pure formatting noise for the diff comparison only: curly vs. straight quotes,
  en/em-dash variants, non-breaking vs. regular spaces, whitespace runs, and Markdown list
  markers. These are display artifacts, not content. (See §6 on the diff harness, which
  normalizes exactly these and nothing else.)

---

## 4. The MUST vs. SHOULD rule

The GFO and the statutes use "must" and "should" with different legal force, and conflating
them is itself an error the rulebook must not make.

- A missing **must** field triggers **mandatory** agency rejection. The SaaS hard-blocks on it.
- A missing **should** field is recommended-but-not-rejection-triggering. The SaaS surfaces it
  as a warning, never a block.

The force is preserved exactly as the source states it. A worked example from the rulebook:
under GFO XII.4.F, Vendor ID is a *should* field, not a *must* field — and this is independently
corroborated by the XII.7.B rejection-code chart, which has a code for an *incorrect* Vendor ID
but none for a *missing* one. A tool that hard-blocked on a missing Vendor ID would be wrong on
the law. Capturing the must/should distinction verbatim is what prevents that class of error.

---

## 5. Each rule's file structure (the four labels)

Every rule lives in its own file in `sources/`. Each file opens with four labels, then the
verbatim text, then a citations list. This format is uniform so any rule can be audited at a
glance.

**The four header labels:**

1. **Name** — the official title of the rule (GFO section title or statute section name).
2. **Date** — the source's own revision/effective date (e.g. "REV. 03/10/2020" for a GFO page,
   or "current revision 2014-09-22" for a statute), plus the page-last-modified date where the
   source shows one.
3. **Issued by** — the authority and where it was published (OSC, OGS, or the NY State
   Legislature via NY Senate Open Legislation), with the chapter/article locator.
4. **Link** — the canonical URL, plus the date the text was copied ("Copied exactly on …").

**Then the body, in two parts:**

- `## STATE TEXT (verbatim)` — the rule itself, exactly as the source states it. Nothing in
  this block is NYS Procurement Vendor's words.
- `## CITATIONS THIS TEXT POINTS TO` — a list of the other statutes, forms, and sections the
  verbatim text references. This is traceability scaffolding for building the product later; it
  is explicitly **not part of the rule** and is labeled as such, so it is never mistaken for
  source text.

The golden copy file itself (`golden-copy-INDEX.md`) is a thin **index**: it lists each rule
with its four labels and a pointer to the source file, organized into domains. The INDEX never
holds rule text — only pointers — so there is exactly one home for each rule's verbatim text and
no risk of two copies drifting apart.

---

## 6. The verification harness (how a rule is proven faithful)

A rule is not "verified" because it looks right. It is verified because a mechanical
word-by-word comparison against the source returned zero content differences. The harness is a
set of small Python scripts; the core one is the diff checker.

**The diff method, step by step:**

1. Capture the source text from primary source (see §8 on capture, including the fallback when a
   page is blocked).
2. Save the raw captured text to a temporary file.
3. Build the rule's source file with the four-label header and the verbatim body.
4. Extract the body — the text between `## STATE TEXT (verbatim)` and `## CITATIONS` — stripping
   only the intentional verbatim markers (a leading lone `*` and a trailing "NB Repealed …"
   line are diffed separately, since they are page markers, not prose).
5. Run the diff checker, which **normalizes formatting noise only** (the quote/dash/whitespace/
   list-marker set named in §3) and then performs a word-level and character-level comparison of
   the body against the capture.

**Reading the result:**

- **PASS** means the comparison found zero content differences — the body is identical to the
  source except for display-only formatting. This is the only acceptable outcome for a rule
  marked verified.
- **FAIL** means a real word or character difference exists. The rule is not entered until the
  difference is found and resolved (it is always either a transcription slip to fix, or — see
  §7 — a genuine source quirk that must be preserved and then diffed correctly).

**The honesty caveat that always travels with a PASS:** a clean diff proves the transcription is
faithful to *the text that was captured*. It does not prove the State has not edited the page
since capture. That is why the capture date is recorded on every file and why freshness checking
(§9) is a permanent obligation, not a one-time step.

**The load-bearing-passage check (the primary method for forms, PDFs, and multi-source captures).**
Where a clean word-level diff is impractical — a PDF whose line breaks rejoin unpredictably, a form
whose fields don't linearize, or a rule assembled from more than one primary source — a
load-bearing-passage check is used instead. A fixed set of critical verbatim strings is enumerated
(section headers, every numbered question's distinctive wording, dollar thresholds, deadline figures,
certification clauses, any operative "must"), and each is confirmed present in the file body, with any
miss flagged and resolved. Apostrophe/dash/markdown variants are normalized before checking, per the
formatting-noise rule in §3, so a flagged "miss" is investigated to confirm it is noise and not a real
gap before it is cleared. This method completed the entire form/PDF domain (the Substitute W-9, the
Invoice Checklist, all four VendRep questionnaires) and the multi-source captures (§109 + AC 3253-S;
the MWBE pass/fail subset). It is weaker than a full word-by-word diff in one specific way — it proves
the enumerated load-bearing strings are present and correct, not that no word anywhere between them
differs — so the enumeration must be deliberately complete, and the count of passages checked is
recorded in the verification log (e.g. "PASS — 28 passages").

**Cross-authority confirmation for stale-risk sources (the discipline that catches what a diff cannot).**
A clean diff proves faithful transcription of *the text captured*; it cannot detect that the captured
source was itself stale or misattributed. Those are the dangerous failures — a stale-but-clean capture
passes its own diff perfectly. So when a rule is captured from a **secondary or compiled source** (for
example, an agency-published compilation PDF of a regulation rather than the live code), the
load-bearing provisions are independently re-confirmed verbatim against a **second live primary
authority** before the file is accepted. Worked example: the MWBE pass/fail file was captured from an
ESD-published reg PDF dated 2020, then its load-bearing provisions (the §142.6 deadline cascade, the
§140.1(kk) thresholds) were re-confirmed against the live, quarterly-updated NYCRR via Cornell LII;
and the XI.4.B budget-variance threshold was confirmed against both the OSC GFO page and the DOB
Contract for Grants face page, which state it identically. Two independent primary sources agreeing
upgrades a rule from indicative to verified. A provision that cannot be cross-confirmed is marked
indicative, not verified, and may not drive a hard-block feature.

---

## 7. Source quirks are preserved, not corrected

The State's published text sometimes contains imperfections. The rulebook reproduces them
verbatim and flags them, rather than silently fixing them, because (a) fidelity is the standard
and (b) a "correction" is a paraphrase by another name and could mask a real difference between
our copy and the source.

Examples actually encountered and preserved:

- **§163** subdivision 4 skips paragraph "f" — the source numbers them e, then g. Preserved as-is.
- **GFO XII.4.B.1** contains source typos ("NYCRRand", "gfochapter-xii"). Preserved verbatim.
- **§139-j, §139-k** carry the State's own "* NB Repealed July 31, 2028" marker; **§163** carries
  "* NB Repealed June 30, 2031". These are reproduced exactly and surfaced as freshness flags.

When a quirk is preserved, the file's header note says so, so a future reader does not mistake it
for a transcription error.

---

## 8. The capture procedure (and the no-reconstruction rule)

**The no-reconstruction rule is the single most important discipline in this manual.** It states:
text only ever enters a source file by being copied from the primary source. It is **never**
reconstructed from memory, from a search-result snippet, or from another AI's paraphrase. If the
primary source cannot be reached, the rule is marked **pending** and left empty — an empty,
honest gap is correct; a plausible-looking reconstruction is a latent error that the verbatim
standard exists to prevent.

**Primary sources, in priority order:** osc.ny.gov (GFO and OSC forms), ogs.ny.gov (OGS-hosted
forms like Appendix A and the Substitute W-9), and nysenate.gov / NY Senate Open Legislation
(statute text, which also shows each section's revision history and current revision date).

**Standard capture:** fetch the page directly, save the raw text, build the file, diff.

**Fallback capture when a page is blocked:** nysenate.gov's bot-detection intermittently blocks
automated fetching of individual statute pages (often while neighboring sections load cleanly).
When this happens, the page is captured from the live site by hand — open it in a browser, copy
the section text (and screenshot the revision-date selector for the date) — and that capture is
then verified by the same word-by-word diff. This is the strongest verification path available
and is how the entire statute domain was completed. The block is per-page and intermittent, so
retrying the direct fetch later is also valid.

**On the role of other AI tools:** another AI (or web search) may be used only to locate
candidate URLs — to find *where* a rule lives. It is never a source of fact. Every claim is
verified against the official page before it enters the rulebook. This guard exists because
paraphrasing tools have, in practice, produced confident-but-false specifics (invented rates,
rounded or wrong deadlines, nonexistent rules). Treat all such output as leads to verify, never
as text to copy.

---

## 9. Freshness — keeping the rulebook current

A verified rule is verified as of its capture date and no later. Laws and GFO pages change. Two
mechanisms keep the rulebook honest over time:

1. **The interest-rate dataset is kept separate from the rulebook.** Interest rates change
   quarterly, so they live in `nys-interest-rates.csv` (a time-series dataset, one row per
   quarter, existing rows immutable), not embedded in any rule. The golden copy *points to* the
   dataset; it never hardcodes a rate, because a frozen rate is wrong within 90 days. Each row
   carries its own source URL and verified-on date.

2. **A freshness check re-verifies pages against their recorded revision dates.** For each rule,
   re-open the canonical URL, compare the source's current revision date to the date recorded in
   the file, and re-run the diff if anything changed. The diff harness in the `tools/` area is
   the seed of this checker (Phase 2 will schedule it).

**Current high-priority freshness targets** (recorded on the relevant files):

- The §179-series prompt-contracting/payment cluster is in active legislative flux. Bills S7001,
  A11179, and S4877 (2025–2026) propose material changes — removing the NFP interest waiver,
  mandating automatic advance payments, changing the registration clock, setting a minimum
  indirect-cost rate. None were enacted as of capture. The current text is captured at its
  pre-amendment state precisely so the change can be diffed when a bill passes.
- Three sections carry scheduled repeal dates: §139-j and §139-k on 2028-07-31; §163 on
  2031-06-30.

---

## 10. The correction-propagation discipline

When a verified source reveals that something elsewhere in the rulebook is wrong, the correction
propagates immediately to every affected file — it is not noted and deferred.

Worked example from the build: verifying GFO XII.5.I established that the general vendor
prompt-payment SFS code is **58401**, not 60740 (60740 is the Capital Projects code; 60311 is
Grants to Others). The earlier draft had used 60740 as the general code. The fix was propagated
the same session to the INDEX and the interest-rate README, each traced to the verifying source.
Likewise, verifying §179-g (and later §179-v) established that vendor prompt-payment interest is
computed on the Tax Law §1096(e) **overpayment** rate — the same column as NFP interest — which
corrected an earlier "indicative underpayment" mapping. The principle: a verified fact outranks
any prior assumption, and the moment one is found, every file resting on the old assumption is
brought into line.

---

## 11. The pain-point layer (a second kind of knowledge, kept separate)

The golden copy records what each rule **says**. It does not record what **goes wrong** at each rule in
practice — the practitioner-level traps that are not in the rule text but get vendors rejected, halted,
or left unpaid. That lived-experience knowledge is real and is the basis for what the product does, but
it is a *different kind* of knowledge from verbatim law, and mixing the two would pollute the golden
copy's whole liability model (its value is that it is the State's exact words, with no NYS Procurement Vendor
commentary). So it lives in a separate, parallel layer of two files:

1. **`PAINPOINT-REGISTER.md` — the evidence layer.** Every practitioner pain-point is recorded here
   first, with its failure mode, the sources that attest to it, and a verification status. A pain-point
   is marked VERIFIED only when (a) it is attested by a primary/authoritative source (an OSC audit, a
   comptroller report, or the statute/GFO provision that creates the trap) or by multiple independent
   practitioner sources that agree, AND (b) the underlying rule it attaches to exists as a verified
   golden-copy source file. Single-source blog claims are marked INDICATIVE and may not drive a
   hard-block feature until upgraded. This is the same evidence discipline the verification report
   applies to rules.

2. **`RISK-MAP.md` — the rule-to-risk / production-spec layer.** For each pain-point, a structured
   entry records the failure mode, the process stage where it bites, the PRE-CHECK a validator should
   implement, the FEATURE it powers, a prevention-vs-recovery tag, and — critically — the exact
   golden-copy source file the rule is grounded in plus the register entry that evidences it. This is
   the layer that makes the product better than a human reviewer: a person carries some traps in memory
   and forgets others under load, whereas this map applies every trap, every time, deterministically.

**The binding rule between the layers:** nothing enters `RISK-MAP.md` without both (a) a verified
golden-copy rule and (b) a `PAINPOINT-REGISTER.md` entry with sources. This is the no-reconstruction
rule (§8) applied to pain-point knowledge — a validator is never built on an assumption.

**Pain-point data is verified before it is recorded**, the same as rule text: a forum or audit claim is
a *lead*, confirmed against a primary source (or corroborated across independent sources) before it
becomes a register entry. NY State-track only; NYC procurement (PASSPort, PPB rules, City Comptroller
registration) is a different regime and is quarantined as context, never used as the rule.

**Scope and compliance frame.** Every feature described in the risk map is an information /
document-validation tool, not financial or legal advice or representation: outputs state what a rule
requires and whether a document meets it. Any recovery-oriented feature (e.g. computing a §179 interest
entitlement a vendor is owed) must clear licensed-attorney oversight before launch and must not drift
into arranging or advising on financing.

These two files are the Phase-2 production engine's specification: the risk map says what each validator
must check, the golden copy says why, and the register holds the evidence. They are deliberately kept
out of the verbatim `sources/` set.

---

## 12. Phasing — what this manual governs and what comes next

- **Phase 1 (the work this manual documents):** build the golden copy — capture, verify, and
  structure the rules — and stand up the pain-point layer (§11) on top of it. Tooling: the Project
  workspace plus web verification and the diff harness. This phase is complete for document-grade
  purposes: 37 verified source files across Domains 1–4 (invoicing/payment, contract approval/NFP
  prompt contracting, vendor onboarding/bid submission, and the underlying statutes), plus the
  `RISK-MAP.md` and `PAINPOINT-REGISTER.md` layer. The remaining optional items (e.g. the three
  VendRep construction attachments) are additive, not blocking.
- **Phase 2 (next):** build the validation engine that reads the golden copy as its authority and the
  risk map (§11) as its check-list spec, and checks vendor documents against both. Tooling: a dedicated
  repository and an agentic coding tool. The freshness checker (§9) is built here, seeded by the diff
  harness.

The boundary the manual draws between "rules are perfect" and "a document passing is not
guaranteed" (§2) carries into Phase 2: the engine enforces the universal rules with confidence
and surfaces — never silently resolves — the per-solicitation and vendor-fact gaps it cannot
verify.

---

## 13. One-page summary of the standard

- Verbatim only. The State's exact words. No paraphrase, no summary, no silent fixes.
- No reconstruction. Copied from primary source or marked pending. Never from memory or a snippet.
- Verify by diff or load-bearing passages. A rule is verified only when a word-by-word diff returns
  zero content differences, or — for forms, PDFs, and multi-source captures — every enumerated
  load-bearing passage is confirmed present. A clean check proves faithful transcription, not that the
  source is unchanged.
- Cross-confirm stale-risk sources. A rule captured from a secondary/compiled source is re-confirmed
  against a second live primary authority before it counts as verified; the failures a diff cannot
  catch are stale-but-clean captures and misattributed sources.
- One home per rule. Each rule in one source file with four labels; the INDEX only points.
- Preserve quirks. Reproduce the source's imperfections and flag them.
- Must vs. should. Hard-block on *must*; warn on *should*. Never conflate them.
- Keep it fresh. Record the capture date; re-verify against revision dates; rates live in a
  separate dataset, never hardcoded.
- Propagate corrections. A verified fact outranks any assumption; fix every affected file at once.
- Other AI finds URLs; it never supplies facts.
- Pain-points are a separate layer. Practitioner traps live in `RISK-MAP.md` + `PAINPOINT-REGISTER.md`,
  never in the verbatim golden copy. Nothing enters the risk map without a verified rule and a sourced
  register entry. Every feature is information/document-validation, not advice.
