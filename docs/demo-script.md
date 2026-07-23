# CareRelay — Hackathon presentation & demo script

**Timebox:** 5 minutes live + 1 minute Q&A buffer  
**Goal:** Judges leave knowing CareRelay is *decision support with a safety gate*, not a chatbot diagnosis tool.

---

## Before you go on stage (2 minutes)

1. Open the **web app** in a clean browser window (full screen). Have `/login` ready.
2. Confirm demo accounts work (login shortcuts on the page):

| Role | Shortcut label | Email | Password |
|------|----------------|-------|----------|
| Patient | Patient journey | `patient@demo.carerelay.local` | `demo-patient` |
| Clinician | Clinical workspace | `clinician@demo.carerelay.local` | `demo-clinician` |
| Reviewer | Review escalations | `reviewer@demo.carerelay.local` | `demo-reviewer` |
| Admin | Safety operations | `admin@demo.carerelay.local` | `demo-admin` |

3. Keep this tab or a notes app with the **paste lines** below. Do not type them live.
4. Optional backup: a second browser window already signed in as clinician (or refresh fast after Sign out).

**If `PROVISION_DEMO_USERS` was never enabled on the host, create/login may fail — fix that before the pitch, not on stage.**

---

## Pitch (45 seconds) — say this first

> CareRelay is an **uncertainty-aware clinical relay**: patients get **urgency guidance**, clinicians get an editable **SOAP draft with provenance**, and anything unsafe fails closed to a **human reviewer**.
>
> We do **not** diagnose or prescribe. Deterministic **red-flag rules run before AI**. Low-risk answers need a **two-key gate** — triage and an independent critic must agree, with enough evidence and low uncertainty. If they don’t, we escalate.

One line for judges:

> **Show the work. Gate the risk. Keep a human in the loop.**

---

## Live demo (about 4 minutes)

### Act 1 — Emergency override (≈70s) · *always works*

**Sign in:** Patient journey → Enter CareRelay.

**Fastest path:** click seeded scenario **Emergency red flag**.

**Or paste into symptom intake (Text mode):**

```text
I have sudden chest pressure and severe shortness of breath.
```

Click **Begin safe intake**.

**What to point at (in order):**

1. **Guidance** — “Seek emergency help now” / Emergency pill.
2. **Gate stamp** — human review / deterministic override (reason `DETERMINISTIC_RED_FLAG`).
3. **Timeline** — red-flag check *before* agents; orchestration **bypassed**.
4. **Citations** — evidence strip (“Evidence used”).
5. **Teach-back** — click the confirm action once.

**Say:**

> Red flags are versioned YAML rules. Chest pressure plus severe shortness of breath never waits on a model. Generative agents are skipped. That’s the safety story.

**Then:** New intake (button on the result screen).

---

### Act 2 — Fail-closed / Same-Day path (≈45s)

**Paste:**

```text
Since last night I have been unable to keep fluids down.
```

Click **Begin safe intake**.

**Expect:** Same-Day guidance (“Qualified review is needed today”), still deterministic for this phrase, with escalation created.

**Say:**

> Same pattern for high-urgency same-day rules. Higher urgency always requires follow-up — we don’t quietly send people home.

*(If you get interview questions instead, answer briefly with “not sure” once or twice — that also tends toward human review. Don’t digress.)*

**Then:** Sign out.

---

### Act 3 — Clinician workspace (≈50s)

**Sign in:** Clinical workspace.

**Do:**

1. Open the latest encounter (patient name **Maya Patient**).
2. Open / point at the **Uncertainty Map** (known facts, missing facts, red flags, retrieval quality).
3. In the SOAP editor, **edit one sentence**, Save if prompted, then **Sign draft**.
4. Point at **sentence provenance** (patient / retrieval / inference labels).

**Say:**

> Clinicians don’t get a black box. They get uncertainty on the left and a draft they must edit and sign. Nothing writes to an EHR without a human.

**Then:** Sign out.

---

### Act 4 — Reviewer escalation (≈40s)

**Sign in:** Review escalations.

**Do:**

1. Find an **open** case → **Claim case**.
2. Resolution note (paste):

```text
Demo review: red-flag path confirmed; patient directed to emergency services; case closed for hackathon handoff.
```

3. **Resolve with audit note**.

**Say:**

> Escalations are durable. Claim and resolve require an audit note — no silent dismissals.

**Then:** Sign out.

---

### Act 5 — Admin / ops (≈35s)

**Sign in:** Safety operations.

**Point at:**

1. **Urgency mix** chart / table (Emergency / Same-Day after your runs).
2. **Rule version** in the hero seal.
3. **Integration posture** (orchestrator / MCP / A2A adapters).
4. **Read-only MCP snapshot** (ops JSON) — isolated from clinical decisions.

**Say:**

> Admins see outcomes and adapter posture, not model theatre. Ops MCP is read-only and never drives urgency.

---

## Close (20 seconds)

> CareRelay bridges patient urgency and clinical documentation with one principle: **if we’re unsure or agents disagree, we fail closed to a person**. Urgency guidance for patients, provenance-rich drafts for clinicians, audit for reviewers and admins.

Invite questions.

---

## Judge Q&A cheat sheet

| Question | Answer |
|----------|--------|
| Is this a diagnosis tool? | No. Urgency classes + plain-language next steps only. Explicit disclaimer everywhere. |
| What if the LLM is wrong? | Red flags override first. Low-risk needs two-key agreement + retrieval + uncertainty bounds. Else escalate. |
| Why Lyzr / agents? | Orchestrate triage, critic, and documentation as separate roles; the **gate** still owns patient-facing urgency. |
| PHI? | Consent required; external calls see PHI-masked text. |
| Production-ready? | Hackathon prototype — not clinically validated; governance required before care use. |
| Stack? | React + FastAPI, Postgres/Redis/Qdrant, deterministic YAML rules, optional Lyzr SuperFlow, read-only ops MCP. |

---

## Extended demo (8 minutes) — if judges want depth

Use after the 5-minute core, or in a booth loop.

### Mild / low-risk path (only if orchestration is healthy)

Paste:

```text
I have mild nasal congestion for one day, it is improving, and I can do normal activities.
```

Answer any interview questions with clear, non-alarming detail (onset today, mild, can do activities, no breathing/chest/weakness issues).

**Ideal show:** Self-Care or Routine + `TWO_KEY_APPROVED` + teach-back.

**If you get Same-Day instead:** Don’t apologize — turn it into the talking point:

> Live agents timed out or disagreed, so we **failed closed** to human review. That’s intentional for a safety product.

### Voice transcript (optional, 20s)

Switch to **Voice transcript**, paste the emergency line if mic/network speech fails, run once to show audit tagging (`voice-transcript`).

### Architecture one-liner for technical judges

> Rules → retrieval → orchestrated agents → **deterministic safety gate** → guidance + SOAP + escalation. Agents propose; the gate decides.

---

## Stage timing card (print / glance)

| Clock | Beat |
|------:|------|
| 0:00 | Pitch: no diagnosis; rules first; two-key; fail closed |
| 0:45 | Patient → Emergency paste → timeline + citations + teach-back |
| 2:00 | New intake → fluids / Same-Day → Sign out |
| 2:45 | Clinician → Uncertainty Map → edit → sign |
| 3:35 | Reviewer → claim → resolve with note |
| 4:15 | Admin → mix, rules, adapters, MCP |
| 4:50 | Close + “questions?” |

---

## Paste bank (keep open)

```text
# Emergency (deterministic)
I have sudden chest pressure and severe shortness of breath.

# Same-Day (deterministic)
Since last night I have been unable to keep fluids down.

# Mild (needs healthy orchestration for Self-Care / Routine)
I have mild nasal congestion for one day, it is improving, and I can do normal activities.

# Reviewer note
Demo review: red-flag path confirmed; patient directed to emergency services; case closed for hackathon handoff.
```

---

## Talking points (repeat if nervous)

1. **No diagnosis** — urgency only.  
2. **Deterministic rules first** — AI cannot override Emergency red flags.  
3. **Two independent safety keys** for low-risk.  
4. **Uncertainty is visible** — map + provenance.  
5. **Fail closed** — disagreement, timeout, weak evidence → human review.  
6. **Human sign-off** — SOAP is a draft until a clinician signs.
