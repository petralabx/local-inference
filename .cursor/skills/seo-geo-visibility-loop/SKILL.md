---
name: seo-geo-visibility-loop
description: Repeatable search + AI-answer visibility loop that audits crawlability, indexation, page intent, titles, internal links, structured data, source citations, and answer-first content, ranks gaps by expected impact, fixes the single highest-leverage issue, then reruns the same crawl and target-query benchmark across search engines and AI answer engines. Repeats until no critical technical issue remains and every priority query maps to a clear answer-ready page. Records test conditions and treats sampled visibility as evidence, not a guaranteed ranking. Use for a public site with defined priority pages and target questions — e.g. "SEO/GEO audit loop", "improve search + AI answer visibility", "generative engine optimization", "rank for these queries".
---

# SEO / GEO Visibility Loop

A repeatable search-visibility workflow that fixes the **highest-impact**
crawl, indexation, page-intent, citation, and answer-readiness gaps first — for
both classic search engines (SEO) and AI answer engines (GEO / generative engine
optimization).

A fixed benchmark keeps this measurable and stops a long list of low-value SEO
chores from crowding out the one fix that actually moves visibility. Mapping each
priority query to one strong, answer-ready page gives search and answer systems a
clear destination.

## The invariant (read this first)

1. **One fixed benchmark.** Same crawl + same target-query set + same engines +
   locale, re-run after each change. Record the conditions every time.
2. **Rank by expected impact; fix one at a time.** Always work the
   highest-leverage gap next, then re-measure — not a flat checklist.
3. **Every priority query maps to one answer-ready page.** That is the GEO goal,
   not keyword stuffing.
4. **Sampled visibility is evidence, not a guarantee.** AI citations and rankings
   vary by time, location, account state, and model. Never promise a ranking.

## When to Use

- A public site with a defined set of priority pages and target questions, where
  you can re-run the same crawl and visibility checks after each change.
- The user says "SEO/GEO audit loop", "improve search/AI-answer visibility",
  "generative engine optimization", or "get our priority pages cited/ranked".

## When NOT to Use

- Internal/authenticated surfaces (e.g. VMC Mission Control) — not crawlable or
  answer-engine-visible; this loop does not apply.
- A one-off copy tweak with no benchmark — just make the edit.
- Pure performance work — use [perf-budget-loop](../perf-budget-loop/SKILL.md)
  (though Core Web Vitals can be one audited dimension here).

## Parameters to define BEFORE starting

```yaml
priority_pages:  [ <the pages that matter> ]
target_queries:  [ <the questions/keywords to win> ]
search_engines:  [ <e.g. Google, Bing> ]
answer_engines:  [ <e.g. AI answer/chat engines you target> ]
locale:          <country/language>
benchmark_method: <how visibility is sampled + recorded>
date:            <run date — results are time-sensitive>
```

Record these in the bundle for **every** measurement; without them the benchmark
is not comparable across rounds.

## Audit dimensions

Audit all of these, then rank findings by expected impact:

1. **Crawlability** — robots, sitemaps, status codes, redirects, render-blocking.
2. **Indexation** — canonical tags, duplicate content, index coverage.
3. **Page intent** — does each priority page match the query's intent?
4. **Titles & metadata** — descriptive, unique, query-aligned.
5. **Internal links** — priority pages reachable and well-linked.
6. **Structured data** — valid schema.org markup for the page type.
7. **Source citations** — credible, citable sourcing (matters for AI answers).
8. **Answer-first content** — the answer is visible, concise, and up top.

## The loop

```text
pin (priority_pages, target_queries, engines, locale, benchmark_method, date)
baseline = audit(all dimensions) + benchmark(target_queries across engines)
record baseline + conditions in the bundle
while critical technical issues remain OR a priority query lacks an answer-ready page
      OR the benchmark still shows a high-impact gap:
    findings = audit(all dimensions)
    ranked   = sort findings by expected impact
    fix(ranked[0])                         # the single highest-leverage gap
    rerun audit(crawl) + benchmark(target_queries across engines)  # SAME conditions
    record results + delta + conditions(date/locale/engine)
return when no critical technical issue remains AND every priority query maps to a
       clear answer-ready page AND the benchmark shows no high-impact gap left
```

## Per-stack backends (delegate, do not reinvent)

| Need | Tool in this stack |
|---|---|
| Fetch/crawl pages, inspect rendered DOM | [autobrowse](../autobrowse/SKILL.md) + `cursor-ide-browser`; QA `advanced_web_crawler` skill |
| Sample search + AI-answer visibility | `WebSearch` / `WebFetch`, recorded with date/locale |
| Core Web Vitals dimension | [perf-budget-loop](../perf-budget-loop/SKILL.md) |
| Implement page/markup fixes + ship | [adversarial-review-loop](../adversarial-review-loop/SKILL.md) for the PR |

Concrete target sites, query lists, and crawl commands live in
[reference.md](reference.md). Note: today the strongest fit is a **public** PLX
surface (marketing / public customer-portal pages), not internal VMC.

## Hard-stop conditions

```yaml
stop_if:
  no_public_crawlable_target: true       # internal-only surface — loop N/A
  benchmark_conditions_unrecorded: true  # results not comparable
  visibility_claimed_as_guaranteed: true # never promise rankings
  fix_requires_unavailable_access: true  # DNS/CMS/registrar access missing -> escalate
```

Hard-stop shape: `stop_reason`, `loop: seo-geo-visibility`, `attempt`,
`failed_checks[]`, `evidence_paths[]`, `next_action` (per `orchestration-kernel` §5).

## Completion contract

Do not report done until all are true:

- No critical technical issue remains (crawl/index/status), with crawl evidence.
- Every priority query maps to one clear, answer-ready page (listed in the report).
- The final benchmark used the **same** queries/engines/locale as the baseline,
  with date/locale/engine recorded for each sample.
- Visibility numbers are presented as sampled evidence with conditions — never as a
  guaranteed ranking.

## Additional resources

- Target sites, query lists, crawl/benchmark commands, worked example: [reference.md](reference.md)
- Shared contracts (evidence bundle, hard-stop): [orchestration-kernel](../orchestration-kernel/SKILL.md)
- Crawl/browse: [autobrowse](../autobrowse/SKILL.md)
- Ship fixes: [adversarial-review-loop](../adversarial-review-loop/SKILL.md)
