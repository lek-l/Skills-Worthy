from dotenv import load_dotenv
import os

load_dotenv()

#jsearch
JSEARCH_BASE_URL = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HOST = "jsearch.p.rapidapi.com"
JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")
JSEARCH_PAGES = 3
JSEARCH_TIMEOUT = 15

#groq — non-reasoning model, no token budget wasted on hidden thinking
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
GROQ_TEMPERATURE = 0.3

#skill extraction
MAX_DESCRIPTIONS = 15
NICHE_SAMPLE_SIZE = 5
TOP_SKILLS_COUNT = 20
MAX_MISSING_SKILLS_SHOWN = 8
MAX_SOFT_SKILLS = 6
CATEGORY_PREVIEW_COUNT = 3

#input validation
MIN_SEARCH_LENGTH = 2
MAX_SEARCH_LENGTH = 100

#canonical acronym map — single source of truth, shared by ai.py and analysis.py
#fixes .title() damage and normalizes display names
ACRONYM_MAP = {
    'Sql': 'SQL', 'Api': 'API', 'Aws': 'AWS', 'Gcp': 'GCP',
    'Bi': 'BI', 'Ai': 'AI', 'Ml': 'ML', 'Etl': 'ETL',
    'Crm': 'CRM', 'Erp': 'ERP', 'Ui': 'UI', 'Ux': 'UX',
    'Css': 'CSS', 'Html': 'HTML', 'Saas': 'SaaS', 'Dbt': 'dbt',
    'Sas': 'SAS', 'Vba': 'VBA', 'Kpi': 'KPI', 'Dag': 'DAG',
    'Nlp': 'NLP', 'Olap': 'OLAP', 'Apis': 'APIs',
    'Node.Js': 'Node.js', 'Nodejs': 'Node.js',
    'Typescript': 'TypeScript', 'Javascript': 'JavaScript',
    'Reactjs': 'React', 'Vuejs': 'Vue',
    'Nextjs': 'Next.js', 'Next.Js': 'Next.js',
    'Graphql': 'GraphQL', 'Mongodb': 'MongoDB',
    'Postgresql': 'PostgreSQL', 'Mysql': 'MySQL',
    'Quickbooks': 'QuickBooks', 'Tensorflow': 'TensorFlow',
    'Pytorch': 'PyTorch', 'Scikit-Learn': 'Scikit-learn',
    'Autocad': 'AutoCAD', 'Solidworks': 'SolidWorks',
    'Matlab': 'MATLAB', 'Spss': 'SPSS',
    'Power Bi': 'Power BI', 'Powerbi': 'Power BI',
    'Bigquery': 'BigQuery', 'Adls Gen2': 'ADLS Gen2',
    'Netsuite': 'NetSuite',
}
