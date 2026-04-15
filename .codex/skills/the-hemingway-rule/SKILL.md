---
name: the-hemingway-rule
description: Use when writing implementation plans, audits, explanations, proposals, or any prose meant for a human reader. Governs writing style, structure, clarity, and decision-surfacing. Invoke whenever the output is more than a code diff.
---

# The Hemingway Rule

Every sentence must do one of three things: explain what is broken, explain why it matters, or tell the reader what to do about it. If a sentence does none of these, delete it.

## Voice

- Write like you are explaining it to a smart colleague over coffee. Not a thesis defense. Not a code review bot.
- Use plain English. If a technical term is unavoidable, define it the first time in a parenthetical.
- Never say "hydrate" when you mean "load." Never say "source of truth" when you mean "the one place this value comes from." Never say "cross-cutting" when you mean "touches several files."
- Do not use words to sound precise when they actually obscure meaning. "Mode-aware helper" means nothing. "A function that checks whether we're in demo or live mode and picks the right cost estimate" means everything.
- Prefer active voice and concrete subjects. "The frontend reads stale state" beats "stale state is being consumed by the rendering layer."

## Structure

### Lead with the punchline

The reader should know what's broken and what to do about it within the first three sentences. Details come after.

Bad:
> #### Current cost flow
> ```
> config/llm_pricing.yaml → token_tracker.py → llm-pricing.ts → Simulation.tsx
> ```
> The UI is using the frontend static estimator, not the backend token estimate endpoint.

Good:
> **The cost estimate is stuck at $0 because demo mode never loads the real provider name.** The frontend falls back to "ollama" (which is free), so the math returns zero. Fix: load the provider from the demo cache on boot, same as we already do for country and use case.

The bad version makes you read a flow diagram before you learn the problem. The good version tells you the problem, why it happens, and what to do — in three lines.

### One heading per decision

Do not organize by "audit findings" and "implementation plan" as separate mega-sections. Organize by problem. Each problem gets:

1. **What's broken** — one to three sentences.
2. **Why** — the root cause, briefly. Include a file path and line only if the reader needs to go look at it. Do not list every file in the call chain.
3. **What to do** — concrete steps. "Update X to do Y" not "consider updating X."
4. **Watch out for** — anything non-obvious that could bite the implementer. Skip this if there's nothing surprising.

### File paths are evidence, not decoration

Only mention a file when the reader needs to open it. If you list six files in a section, the reader opens zero. If you list one, they open one.

Bad:
> Relevant files:
> - `frontend/src/pages/Simulation.tsx`
> - `frontend/src/lib/llm-pricing.ts`
> - `frontend/src/contexts/AppContext.tsx`
> - `frontend/src/lib/console-api.ts`
> - `backend/src/miroworld/services/console_service.py`
> - `backend/src/miroworld/services/token_tracker.py`
> - `config/llm_pricing.yaml`

Good:
> The cost badge is rendered in `Simulation.tsx` using a static estimate from `llm-pricing.ts`. The provider name it needs comes from `AppContext.tsx`, which currently doesn't load it from the demo cache.

Three files, each with a reason for being mentioned.

### Code snippets are for the surprising parts

Do not paste code that says what the prose already said. Paste code only when the reader would not believe you otherwise, or when the exact syntax matters for the fix.

Bad (after already explaining the problem in words):
> ```python
> def get_interactions(self, simulation_id: str) -> list[dict[str, Any]]:
>     with self._connect() as conn:
>         rows = conn.execute(
>             "SELECT * FROM interactions WHERE simulation_id = ? ORDER BY round_no, id",
>             (simulation_id,),
>         ).fetchall()
>     return [dict(r) for r in rows]
> ```

The reader did not need to see a straightforward SELECT statement. Save code blocks for the weird parts — the scoring formula, the regex, the edge case.

## Length

### The 30-second rule

A busy human should understand the entire plan in 30 seconds of skimming. That means:

- The top of the document has a 3–5 bullet summary of every problem and its fix.
- Each section is at most one screen of text (roughly 20 lines of prose).
- If a section needs to be longer, it should be split into sub-problems.

### Kill the filler

These add zero information and should never appear:

- "This is smaller, lower risk, and already has a failing regression test." → Just say "Fix this first — there's already a failing test for it."
- "That creates drift risk." → Say what actually happens: "The frontend and backend estimates will eventually disagree."
- "Do not introduce a fake fallback estimate when the provider/model is missing." → This is a constraint that matters. But say it as: "If the provider is unknown, show 'cost unavailable' — don't guess."

### Avoid the audit treadmill

Do not list every function in a call chain just because you read them. The reader needs to know:
- Where the bug is (one location).
- What feeds into it (one or two upstream points).
- What consumes its output (one or two downstream points).

Not the complete genealogy of every function involved.

## Decisions and watchouts

### Surface decisions explicitly

If the implementer has a choice to make, say so. Use a callout:

> **Decision needed:** Should the backend estimate endpoint replace the frontend static math entirely, or should demo-static keep the frontend path since it can't call the backend?

Do not bury decisions inside prose. The reader will miss them.

### Watchouts go at the end of each section, not in a separate megalist

Bad:
> ### Important constraint
> Do not add heuristic "word splitter" logic for unknown collapsed strings like:
> - `medicalorhealthservicesmanager`
> - `teacherorinstructor`

Good (at the end of the normalization section):
> **Watch out:** Some occupation labels arrive pre-collapsed with no separators (e.g. `medicalorhealthservicesmanager`). These can't be split reliably with regex. Don't try. If we need them clean, it has to come from a lookup table or dataset preprocessing — not a runtime heuristic.

Same information, but placed where the implementer will read it while doing the work.

## Test recommendations

Keep test descriptions to one line each. The implementer knows how to write tests. They need to know *what to test*, not *how tests work*.

Bad:
> - `frontend/src/pages/Simulation.test.tsx`
>   - demo-static hydrates provider/model from bundled cache
>   - cost is non-zero for Gemini/OpenAI cached runs
>   - cost changes when rounds slider changes

Good:
> Tests to add: demo-static cost is non-zero after boot; cost updates when the slider moves; provider/model come from the demo cache, not defaults.

## Sentence rhythm

Vary your sentence lengths. Three medium sentences in a row put the reader to sleep. Follow a long explanation with a short punch. Then expand again.

Bad:
> The badge is rendered in Simulation.tsx with the frontend helper in llm-pricing.ts. That helper needs the provider and model name. In demo-static, AppContext.tsx loads the cached session, country, use case, rounds, and population, but it does not load the cached provider and model from demo.source_run. The app then falls back to the default provider, which is ollama, and ollama is priced at zero.

Every sentence is ~20 words. Same rhythm, same structure. The reader's eyes glaze. Try:

> The cost badge calls a pricing helper that needs the provider name. Demo-static never loads it. So the app defaults to "ollama" — which is free — and the math returns $0.

Three sentences. Long, short, long. The short one lands like a punch.

### Do not narrate your own reasoning

Bad:
> This matters because the cost fix is not the same in all three modes.

The reader can figure out *why* you told them something. Just tell them the thing. If you explain the three modes, the reader will understand why it matters. You do not need a sentence that says "this is relevant."

Similarly, never write:
- "It is worth noting that..."
- "An important distinction here is..."
- "There is a second issue here."

Just state the second issue.

### Drop the safety hedges

Bad:
> It also gives the wrong impression that the slider is broken, even when the math is running.

If the cost reads $0, the slider *looks* broken. Say that. Do not soften it with "gives the wrong impression." The reader is the person who reported the bug — they know it looks broken.

Bad:
> It cannot reliably repair broken occupation strings after the fact.

Good:
> It can't fix these.

If you have already explained what "these" are and where "after the fact" means, you do not need to re-specify. Trust the reader's short-term memory.

## Say it once

If the document has a summary at the top, a detailed section in the middle, and a "short version" at the bottom, you have said everything three times. The reader who skims reads the summary. The reader who needs detail reads the section. Nobody reads both and then also reads a recap.

Pick two at most:
- A top-level summary (3–5 bullets)
- Detailed sections

Or:
- Detailed sections
- A bottom-line recap (only if the document is very long, 5+ sections)

Never all three. If you feel the need for a recap, your sections are too long.

## The banned word list

These words make prose sound technical without adding precision. Replace them every time.

| Instead of | Write |
|---|---|
| hydrate | load |
| source of truth | the one place this value lives |
| cross-cutting | touches several files |
| mode-aware | checks which mode we're in |
| drift risk | the two estimates will eventually disagree |
| containment fix | small, safe fix |
| invasive change | bigger change, touches more files |
| side effects | breaks other things |
| surface (as a verb) | show / expose / call out |
| leverage (as a verb) | use |
| utilize | use |
| facilitate | help / enable |
| architecting | designing |
| orthogonal | unrelated |
| non-trivial | hard / complicated |

If you catch yourself reaching for a fancy word, ask: would I say this out loud to a person? If not, use the word you would actually say.

## Flow diagrams

ASCII flow diagrams are useful when the reader needs to see a branching path or a sequence with more than three steps. They are not useful when they restate what the preceding paragraph already said.

Bad (after a paragraph explaining the same thing):
> ```text
> demo-static boot
>     |
>     +-- loads rounds, questions, population
>     |
>     X  does not load provider/model
>     |
>     v
> default provider = ollama
> ```

The paragraph already told the reader this. The diagram is decorative repetition. Use a diagram only when the branching or sequencing is genuinely hard to follow in prose — for example, three modes that hit three different code paths.

Good use of a diagram:
> ```text
> live        → backend estimate API
> demo        → backend estimate API (cached data)
> demo-static → frontend static helper (no backend)
> ```

This shows a three-way branch that would be awkward as a paragraph. It earns its space.

## The checklist

You can use this handy checklist to audit your own writing: 

- [ ] Can a reader skim the first three lines and know what's broken and what to do?
- [ ] Is every file path mentioned because the reader needs to open it?
- [ ] Is every code block showing something the prose didn't already explain?
- [ ] Are decisions called out explicitly, not buried?
- [ ] Is the total length under 2 pages per problem?
- [ ] Did you use the simplest possible word for every concept?
- [ ] Would you be comfortable reading this aloud to someone? If it sounds stilted, rewrite it.
- [ ] Do your sentence lengths vary? Read three consecutive sentences — if they are all the same length, rewrite one.
- [ ] Did you say the same thing in both a summary and a section? Cut one.
- [ ] Is every word on the banned list replaced with its plain equivalent?
- [ ] Does every diagram show something the prose did not already explain?
