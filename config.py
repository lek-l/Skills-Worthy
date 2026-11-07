from dotenv import load_dotenv
import os

load_dotenv()

#jsearch
JSEARCH_BASE_URL = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HOST = "jsearch.p.rapidapi.com"
JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")
JSEARCH_PAGES = 3
JSEARCH_TIMEOUT = 15

#groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
#groq model, read from the environment so the next deprecation is a settings change
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_REASONING_EFFORT = os.getenv("GROQ_REASONING_EFFORT", "low")
#extra tokens added to every request so hidden reasoning cannot crowd out the visible answer
GROQ_REASONING_HEADROOM = 300
GROQ_TEMPERATURE = 0.3

#skill extraction
DESCRIPTION_BATCH_SIZE = 3
MAX_DESCRIPTIONS = 15
TOP_SKILLS_COUNT = 20
MAX_MISSING_SKILLS_SHOWN = 8
MAX_SOFT_SKILLS = 6
CATEGORY_PREVIEW_COUNT = 3

#input validation
MIN_SEARCH_LENGTH = 2
MAX_SEARCH_LENGTH = 100

#canonical acronym map — single source of truth, shared by ai.py and analysis.py
ACRONYM_MAP = {
    'Sql': 'SQL', 'Api': 'API', 'Aws': 'AWS', 'Gcp': 'GCP',
    'Bi': 'BI', 'Ai': 'AI', 'Ml': 'ML', 'Etl': 'ETL',
    'Crm': 'CRM', 'Erp': 'ERP', 'Ui': 'UI', 'Ux': 'UX',
    'Css': 'CSS', 'Html': 'HTML', 'Saas': 'SaaS', 'Dbt': 'dbt',
    'Sas': 'SAS', 'Vba': 'VBA', 'Kpi': 'KPI', 'Dag': 'DAG',
    'Nlp': 'NLP', 'Olap': 'OLAP', 'Apis': 'APIs',
    'Adls Gen2': 'ADLS Gen2',
}