# Skills Worthy

*What does the job market actually want right now?*

I kept asking myself this during my own job search. Every job board showed me postings, but none of them told me which skills kept showing up across all of them. What should I actually be learning? What are some non-negotiables for the roles I want?

I could not find a tool that answered that, and so I built one.

**[skills-worthy-1.streamlit.app](https://skills-worthy-1.streamlit.app)**

---

## What it does

Skills Worthy pulls live job postings for any role you search, then it extracts the technical skills that are mentioned in the postings, and turns them into something actionable.

Search data analyst. You will get a frequency-ranked breakdown of every skill across real postings, split into priority tier list, then summarized by AI, and lastly, with a personalized skill gap analysis if you want one.

The core idea is **let the LLM identify, let Python count.** Groq reads each job description and extracts skill names. Python then aggregates the frequencies. That separation keeps the counts accurate and deterministic even when the model output varies.

---

## How to use it

**1. Search a role**  
Type any job title: *data analyst*, *machine learning engineer*, *quant analyst*, *fintech developer*. More specific searches will give you more targeted results.

**2. Read the skill chart**  
The bar chart ranks every technical skill found across live postings by how often it appears. Brighter bar = more employers asking for it.

**3. Check the priority tiers**  
Skills split into three tiers by frequency:
- **Must Have**: shows up in most postings, non-negotiable
- **Good To Have**: appears often enough to be a real differentiator
- **Nice To Have**: mentioned occasionally, worth knowing but not critical

**4. Read the AI insight**  
A tight 2-sentence market summary built from the extracted skills, covering what the role looks like right now and where to focus.

**5. Run your skill gap**  
Enter your current skills as a comma-separated list (`Python, SQL, Excel`). You will see your overlap percentage, which skills you already have, which you're missing, and a 5-step learning roadmap prioritized by demand.

---

## How it works

```
search query
    │
    ├── JSearch API — 3 pages fetched in parallel
    │       └── filter by title match → pull descriptions
    │
    └── Groq LLaMA 3.3 70B
            ├── extract skills per posting in batches
            │       └── normalize aliases → Python counts with Counter
            │
            └── parallel calls for:
                    ├── market insight
                    ├── soft skills
                    └── skill categorization
                            │
                            └── compute tiers → render in Streamlit
```

A few decisions worth calling out:

- **Parallel fetching**: JSearch pages and Groq pipeline calls run concurrently, cutting total latency significantly vs sequential requests
- **Alias normalization**: `js → JavaScript`, `sklearn → Scikit-learn`, etc. so skill variants don't split the frequency count
- **Roadmap caching**: keyed on `(role, user_skills)` in session state, so Groq only fires when the input actually changes

---

## Libraries

| Library | Why I used it |
|---|---|
| **Streamlit** | Turns Python into a deployable web app without touching any frontend code, perfect for data-heavy tools like this |
| **Groq** | Fast LLM inference running LLaMA 3.3 70B, handles skill extraction, insight generation, soft skills, and roadmap writing. Free tier made it viable |
| **Requests** | Clean HTTP client for the JSearch API, handles timeouts and error responses without extra complexity |
| **Pandas** | Structures skill counts into dataframes for filtering, sorting, and passing to Plotly |
| **Plotly Express** | Renders the interactive bar chart, cleaner output than Matplotlib and integrates natively with Streamlit |
| **Collections.Counter** | Python stdlib, fast, exact frequency counting across all postings, no external dependency needed |
| **python-dotenv** | Loads API keys locally from `.env`, on Streamlit Cloud, keys come from the secrets manager instead |
| **concurrent.futures** | Python stdlib, runs parallel threads for JSearch fetches and Groq calls, cuts wait time significantly |

---

## Stack

`Python` · `Streamlit` · `Groq API (LLaMA 3.3 70B)` · `JSearch API` · `Plotly` · `Pandas`  
Deployed on Streamlit Cloud.

---

## Run it locally

```bash
git clone https://github.com/lek-l/Skills-Worthy.git
cd Skills-Worthy
pip install -r requirements.txt
```

Create a `.env` file:
```
JSEARCH_API_KEY=your_key
GROQ_API_KEY=your_key
```

Both are free:
- Groq → [console.groq.com](https://console.groq.com)
- JSearch → [rapidapi.com](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)

```bash
streamlit run app.py
```

---

## A few caveats

Broad roles like *product manager* pull a wide mix of subtypes from JSearch: technical PM, data PM, general PM, which can produce a wider-than-expected skill set. That's a data quality limitation on the API side, not a bug. Very niche roles may not have enough postings for meaningful extraction. The app handles both cases with a clear message instead of crashing.

Results are live and vary by day.

---

## Project structure

```
app.py          Streamlit UI and page layout
ai.py           Groq skill extraction, normalization, tiers, roadmap generation
analysis.py     Job processing, dataframe building, skill gap computation
api.py          JSearch client with parallel page fetching
config.py       Constants and canonical skill alias map
state.py        Streamlit session state management
```
