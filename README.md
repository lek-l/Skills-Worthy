# Skills Worthy

A job market intelligence tool that shows which skills employers actually ask for, ranked across live job postings.

**[skills-worthy-1.streamlit.app](https://skills-worthy-1.streamlit.app)**

## Why I built it

During my own job search I kept asking the same question: which skills actually matter for the roles I want? Every job board showed me postings, but none of them told me which skills kept appearing across all of them. I could not find a tool that answered that, so I built one.

## What it does

Skills Worthy pulls live job postings for any role you search, extracts the technical skills mentioned across them, and turns the result into something you can act on: a frequency-ranked chart, a priority tier list, a short market summary, and a personalized skill-gap analysis.

## How to use it

1. **Search a role.** Type any job title, such as data analyst, product manager, or machine learning engineer. More specific searches return more targeted results.
2. **Read the skill chart.** Every technical skill found across the postings, ranked by how often it appears. A brighter bar means more employers ask for it.
3. **Check the priority tiers.** Skills split into Must Have, Good To Have, and Nice To Have, ranked by demand.
4. **Read the market insight.** A short, generated summary of what the role looks like right now and where to focus.
5. **Run your skill gap.** Enter the skills you already have. You get your overlap percentage, what you already match, what you are missing, and a prioritized learning roadmap.

## How it works

The core idea: let the language model identify, let Python count.

1. **Fetch.** The app queries the JSearch API for live postings, two pages in parallel.
2. **Filter.** It keeps only postings whose title matches every word in your search, so a search for "data analyst" does not pull in "data engineer."
3. **Extract.** A regex taxonomy of 518 skills across 30 domains scans every description in Python, with no API calls and fully deterministic counting. One model call then reads a short sample to surface niche skills the taxonomy does not know, and Python counts those across the postings too.
4. **Rank.** Skills are grouped into tiers by frequency: the most-requested are Must Have, the next most-requested Good To Have, the rest Nice To Have.
5. **Summarize.** A separate model call writes the two-sentence market insight.
6. **Render.** Results display in a tabbed Streamlit interface with a Plotly chart.

This separation keeps the counts accurate even when model output varies: the model is used for recognition, never for arithmetic.

## Design decisions

- **Hybrid extraction over pure LLM.** Asking the model to both find and count skills produced unreliable frequencies. Moving the counting into Python made the numbers deterministic and cut the model calls from more than fifteen per search to three.
- **Position-based tiers.** Tiers rank by how many postings mention each skill rather than by a fixed percentage cutoff, so roles with spread-out demand still produce useful tiers instead of a near-empty Must Have.
- **Honest failure messages.** Rate limits, authentication failures, timeouts, and network errors each return a distinct message, so a user always knows whether to retry or wait.
- **Partial results are never cached.** If some pages fail, the app shows what it got but does not store the thin result, so the next visitor gets a full fetch.
- **Quota protection.** A shared cache serves repeat searches without new API calls, and a per-session cap keeps one visitor from exhausting the free-tier quota for everyone.

## Tech stack

| Library | Role |
|---|---|
| Streamlit | Web interface, no separate frontend needed |
| Groq (qwen) | Fast model inference for niche-skill discovery, insight, and roadmap |
| JSearch (RapidAPI) | Live job posting data |
| Pandas | Structuring skill counts for ranking and charting |
| Plotly | The interactive skill-frequency chart |

## Testing

The project has 119 tests covering the extraction pipeline, tier logic, skill-gap matching, API error handling, and session state. API calls are mocked, so the suite runs without live keys and verifies behavior such as partial-fetch handling, rate-limit messaging, and the deterministic counting logic.

## Known limitations

- **Free-tier API.** JSearch allows 200 requests per month, which is roughly 100 searches at two pages each. Heavy use can exhaust the monthly quota.
- **Latency.** Average JSearch response time is near 11 seconds, so a search is not instant.
- **Sample size.** Extraction analyzes up to 15 postings per search, which is enough for a strong signal but not exhaustive.
- **No database yet.** The app has no persistence or SQL layer. A planned second project pairs a public dataset with SQL and a BI tool to cover that ground.