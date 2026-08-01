# seo-geo-visibility-loop — reference

Repo-specific wiring for the universal loop in [SKILL.md](SKILL.md). Keep
`SKILL.md` portable; target sites, query lists, and commands live here.

## 1. Where this loop applies (and where it does not)

- **Applies:** public, crawlable surfaces — PLX marketing/public pages and any
  public-facing customer-portal pages. These are reachable by search crawlers and
  AI answer engines, so visibility work is meaningful.
- **Does NOT apply:** VMC Mission Control (`/vmc/*`) and any authenticated/internal
  app. They are not crawlable or answer-engine-visible — running this loop there is
  a hard stop (`no_public_crawlable_target`).

Confirm the target is a public URL before pinning `PARAMS.md`.

## 2. Tooling map

| Step | How, in this stack |
|---|---|
| Crawl + render inspection | [autobrowse](../autobrowse/SKILL.md) and `cursor-ide-browser` (snapshot the rendered DOM, read status/redirects); QA `advanced_web_crawler` skill for structured extraction |
| Status/headers/robots/sitemap | `Shell` with `curl -I` for status/redirects; fetch `/robots.txt` and `/sitemap.xml` |
| Search + AI-answer sampling | `WebSearch` / `WebFetch`, each sample tagged with date + locale + engine |
| Structured-data validation | inspect `application/ld+json` blocks in the rendered DOM against schema.org for the page type |
| Core Web Vitals dimension | delegate to [perf-budget-loop](../perf-budget-loop/SKILL.md) (LCP/CLS/INP) |
| Ship the fix | [adversarial-review-loop](../adversarial-review-loop/SKILL.md) — open a PR on the site's repo (e.g. plx-customer-portal `staging`) |

## 3. Recording conditions (mandatory, every sample)

AI citations and search results vary by time, location, account state, and model.
Each benchmark sample MUST record:

```yaml
query: <the target query>
engine: <search or answer engine>
locale: <country/language>
date: <ISO date/time of the sample>
result: <position / cited? / answer snippet captured>
```

Treat the sample as evidence of a trend, never as a guaranteed ranking. Re-run the
SAME query/engine/locale set each round so deltas are comparable.

## 4. Impact ranking heuristic

When ranking findings, prefer fixes that unblock the most query→page paths:

1. **Critical technical** (blocks indexing): non-200 status, `noindex` on a
   priority page, broken canonical, missing/blocked sitemap → always first.
2. **Intent/answer gaps**: a priority query with no answer-ready page, or the
   answer buried below the fold → high.
3. **Structured data / citations**: missing schema or weak sourcing on otherwise
   good pages → medium-high (matters more for AI answers).
4. **Metadata/internal-linking polish**: titles, descriptions, link depth → medium.

Fix the single highest-ranked item, then re-measure before picking the next.

## 5. Evidence bundle layout

```text
.orchestrator/seo-geo-<slug>/
├── PARAMS.md            # priority_pages, target_queries, engines, locale, method, date
├── baseline.json        # audit findings + per-query visibility samples (with conditions)
├── rounds/<k>/
│   ├── finding.md       # the ranked gap fixed this round
│   ├── fix.diff         # page/markup change (or PR link)
│   └── benchmark.json   # re-sampled visibility + delta + conditions
└── REPORT.md            # remaining issues, query->page map, sampled visibility w/ caveats
```

## 6. Worked example (public PLX page)

```text
PARAMS: priority_pages=[/contract-manufacturing], target_queries=["private label skincare manufacturer"],
        search_engines=[Google,Bing], answer_engines=[an AI answer engine],
        locale=US-en, method="top-10 + cited?", date=2026-06-19

baseline: page returns 200 but has noindex (critical), no FAQ schema, answer buried
round 1: remove noindex on the priority page (critical technical) -> re-crawl: indexable
round 2: add answer-first H1 + concise summary + FAQ schema.org markup
         -> re-sample queries (same engines/locale/date-tagged): page now appears p8 Google, cited in 1 answer engine
round 3: add internal links from 3 related pages + tighten title
         -> re-sample: p4 Google, cited in 2 answer engines; no critical issues remain
return: no critical technical issue; the priority query maps to an answer-ready page;
        report presents visibility as sampled evidence with date/locale/engine, not a guarantee
```
