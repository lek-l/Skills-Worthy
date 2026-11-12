import re
from collections import Counter

#skill taxonomy — canonical names mapped to regex patterns for matching in job descriptions
#patterns are case-insensitive with word boundaries to prevent substring false positives
#this is the deterministic half of the hybrid extraction pipeline:
#  taxonomy handles the ~200 most common skills instantly in python
#  groq handles niche or emerging tools the taxonomy doesn't know about

def _wp(term):
    #word pattern — wraps a term in word boundaries for regex matching
    return rf'\b{re.escape(term)}\b'

def _build(name, *patterns):
    #compiles one or more patterns into a single case-insensitive regex
    combined = '|'.join(patterns)
    return (name, re.compile(combined, re.IGNORECASE))

#the taxonomy — organized by domain for maintainability
#each entry: (canonical_display_name, compiled_regex)
_TAXONOMY = dict([

    #programming languages
    _build('Python', _wp('python'), _wp('python3')),
    _build('Java', _wp('java') + r'(?!script)'),
    _build('JavaScript', _wp('javascript'), r'\bjs\b(?!\.)'),
    _build('TypeScript', _wp('typescript'), _wp('ts') + r'(?!\b[A-Z])'),
    _build('C++', r'\bc\+\+\b'),
    _build('C#', r'\bc#\b', _wp('c sharp'), _wp('csharp')),
    _build('Go', _wp('golang'), _wp('go language'), _wp('go programming')),
    _build('Rust', _wp('rust') + r'(?=.*(?:programming|developer|engineer|lang))'),
    _build('Ruby', _wp('ruby')),
    _build('PHP', _wp('php')),
    _build('Scala', _wp('scala')),
    _build('Kotlin', _wp('kotlin')),
    _build('Swift', _wp('swift') + r'(?=.*(?:ios|mobile|apple|programming|developer))'),
    _build('R', r'(?<![A-Za-z/])R(?![A-Za-z/])', _wp('r programming'), _wp('r language'),
           _wp('rstudio'), _wp('r studio')),
    _build('MATLAB', _wp('matlab')),
    _build('SAS', _wp('sas') + r'(?=.*(?:analytics|statistic|programming|data|enterprise))'),
    _build('SPSS', _wp('spss')),
    _build('VBA', _wp('vba'), _wp('visual basic')),
    _build('Julia', _wp('julia') + r'(?=.*(?:programming|language|data|scientific))'),
    _build('Perl', _wp('perl')),
    _build('Dart', _wp('dart') + r'(?=.*(?:flutter|mobile|programming))'),
    _build('Lua', _wp('lua') + r'(?=.*(?:scripting|programming|game))'),
    _build('Bash', _wp('bash'), _wp('shell scripting')),
    _build('PowerShell', _wp('powershell')),

    #databases
    _build('SQL', _wp('sql') + r'(?!\s*server)'),
    _build('MySQL', _wp('mysql')),
    _build('PostgreSQL', _wp('postgresql'), _wp('postgres')),
    _build('MongoDB', _wp('mongodb'), _wp('mongo')),
    _build('Redis', _wp('redis')),
    _build('Cassandra', _wp('cassandra')),
    _build('DynamoDB', _wp('dynamodb')),
    _build('SQLite', _wp('sqlite')),
    _build('Oracle Database', _wp('oracle') + r'(?=.*(?:database|db|sql|plsql))'),
    _build('SQL Server', _wp('sql server'), _wp('mssql'), _wp('ms sql')),
    _build('MariaDB', _wp('mariadb')),
    _build('Neo4j', _wp('neo4j')),
    _build('Firebase', _wp('firebase')),
    _build('Supabase', _wp('supabase')),
    _build('Elasticsearch', _wp('elasticsearch'), _wp('elastic search')),
    _build('Couchbase', _wp('couchbase')),

    #cloud and infrastructure
    _build('AWS', _wp('aws'), _wp('amazon web services')),
    _build('Azure', _wp('azure')),
    _build('Google Cloud', _wp('gcp'), _wp('google cloud')),
    _build('Terraform', _wp('terraform')),
    _build('Ansible', _wp('ansible')),
    _build('Docker', _wp('docker')),
    _build('Kubernetes', _wp('kubernetes'), _wp('k8s')),
    _build('Heroku', _wp('heroku')),
    _build('CloudFormation', _wp('cloudformation')),
    _build('Lambda', _wp('aws lambda'), _wp('lambda') + r'(?=.*(?:aws|serverless|function))'),

    #data warehouses and pipelines
    _build('Snowflake', _wp('snowflake')),
    _build('BigQuery', _wp('bigquery'), _wp('big query')),
    _build('Redshift', _wp('redshift')),
    _build('Databricks', _wp('databricks')),
    _build('dbt', _wp('dbt'), _wp('data build tool')),
    _build('Apache Spark', _wp('spark'), _wp('pyspark')),
    _build('Apache Airflow', _wp('airflow')),
    _build('Apache Kafka', _wp('kafka')),
    _build('Apache Hive', _wp('hive')),
    _build('ETL', _wp('etl')),
    _build('SSIS', _wp('ssis')),
    _build('Informatica', _wp('informatica')),
    _build('Talend', _wp('talend')),
    _build('Fivetran', _wp('fivetran')),
    _build('Stitch', _wp('stitch') + r'(?=.*(?:data|etl|pipeline|integration))'),
    _build('Apache NiFi', _wp('nifi')),

    #data analysis and visualization
    _build('Excel', _wp('excel'), _wp('spreadsheet')),
    _build('Tableau', _wp('tableau')),
    _build('Power BI', _wp('power bi'), _wp('powerbi'), r'power\s*bi'),
    _build('Looker', _wp('looker')),
    _build('Google Analytics', _wp('google analytics'), _wp('ga4')),
    _build('Mixpanel', _wp('mixpanel')),
    _build('Amplitude', _wp('amplitude') + r'(?=.*(?:analytics|data|product))'),
    _build('pandas', _wp('pandas')),
    _build('NumPy', _wp('numpy')),
    _build('SciPy', _wp('scipy')),
    _build('Matplotlib', _wp('matplotlib')),
    _build('Seaborn', _wp('seaborn')),
    _build('D3.js', _wp('d3'), _wp('d3.js')),
    _build('Plotly', _wp('plotly')),
    _build('Grafana', _wp('grafana')),
    _build('Qlik', _wp('qlik'), _wp('qlikview'), _wp('qliksense')),
    _build('SSRS', _wp('ssrs')),
    _build('DAX', _wp('dax')),
    _build('Power Query', _wp('power query')),
    _build('Google Sheets', _wp('google sheets')),
    _build('Alteryx', _wp('alteryx')),
    _build('KNIME', _wp('knime')),
    _build('SAS Viya', _wp('sas viya')),
    _build('Stata', _wp('stata')),
    _build('Minitab', _wp('minitab')),

    #machine learning and ai
    _build('TensorFlow', _wp('tensorflow')),
    _build('PyTorch', _wp('pytorch')),
    _build('Scikit-learn', _wp('scikit'), _wp('sklearn')),
    _build('Keras', _wp('keras')),
    _build('XGBoost', _wp('xgboost')),
    _build('LightGBM', _wp('lightgbm')),
    _build('Hugging Face', _wp('hugging face'), _wp('huggingface')),
    _build('OpenCV', _wp('opencv')),
    _build('NLTK', _wp('nltk')),
    _build('spaCy', _wp('spacy')),
    _build('MLflow', _wp('mlflow')),
    _build('Kubeflow', _wp('kubeflow')),
    _build('SageMaker', _wp('sagemaker')),
    _build('OpenAI', _wp('openai')),
    _build('LangChain', _wp('langchain')),

    #web frameworks
    _build('React', _wp('react'), _wp('reactjs'), _wp('react.js')),
    _build('Angular', _wp('angular')),
    _build('Vue', _wp('vue'), _wp('vuejs'), _wp('vue.js')),
    _build('Next.js', _wp('next.js'), _wp('nextjs')),
    _build('Django', _wp('django')),
    _build('Flask', _wp('flask')),
    _build('FastAPI', _wp('fastapi')),
    _build('Express', _wp('express.js'), _wp('expressjs')),
    _build('Spring Boot', _wp('spring boot'), _wp('spring') + r'(?=.*(?:boot|java|framework))'),
    _build('Node.js', _wp('node.js'), _wp('nodejs'), _wp('node') + r'(?=.*(?:js|javascript|express|npm))'),
    _build('Rails', _wp('ruby on rails'), _wp('rails')),
    _build('Laravel', _wp('laravel')),
    _build('ASP.NET', _wp('asp.net'), _wp('dotnet'), _wp('.net')),
    _build('Svelte', _wp('svelte')),
    _build('Nuxt', _wp('nuxt')),
    _build('Gatsby', _wp('gatsby')),
    _build('HTML', _wp('html'), _wp('html5')),
    _build('CSS', _wp('css'), _wp('css3')),
    _build('Tailwind', _wp('tailwind')),
    _build('Bootstrap', _wp('bootstrap')),
    _build('jQuery', _wp('jquery')),
    _build('Redux', _wp('redux')),
    _build('Webpack', _wp('webpack')),

    #devops and ci/cd
    _build('Jenkins', _wp('jenkins')),
    _build('GitHub Actions', _wp('github actions')),
    _build('GitLab CI', _wp('gitlab ci')),
    _build('CircleCI', _wp('circleci')),
    _build('Travis CI', _wp('travis')),
    _build('ArgoCD', _wp('argocd'), _wp('argo cd')),
    _build('Prometheus', _wp('prometheus')),
    _build('Datadog', _wp('datadog')),
    _build('Splunk', _wp('splunk')),
    _build('New Relic', _wp('new relic')),
    _build('Nginx', _wp('nginx')),
    _build('Apache HTTP', _wp('apache') + r'(?=.*(?:http|server|web))'),

    #version control
    _build('Git', _wp('git') + r'(?!hub|lab)'),
    _build('GitHub', _wp('github')),
    _build('GitLab', _wp('gitlab')),
    _build('Bitbucket', _wp('bitbucket')),

    #project and business tools
    _build('Jira', _wp('jira')),
    _build('Confluence', _wp('confluence')),
    _build('Trello', _wp('trello')),
    _build('Asana', _wp('asana')),
    _build('Monday.com', _wp('monday.com')),
    _build('Notion', _wp('notion') + r'(?=.*(?:project|tool|workspace|documentation))'),
    _build('Linear', _wp('linear') + r'(?=.*(?:project|issue|ticket|tool))'),
    _build('Slack', _wp('slack') + r'(?=.*(?:communication|team|tool|channel))'),
    _build('Salesforce', _wp('salesforce'), _wp('sfdc')),
    _build('SAP', _wp('sap') + r'(?=.*(?:erp|module|system|hana|enterprise))'),
    _build('Oracle ERP', _wp('oracle') + r'(?=.*(?:erp|financials|cloud|fusion))'),
    _build('HubSpot', _wp('hubspot')),
    _build('Zendesk', _wp('zendesk')),
    _build('ServiceNow', _wp('servicenow')),
    _build('Workday', _wp('workday')),
    _build('QuickBooks', _wp('quickbooks')),
    _build('Xero', _wp('xero')),
    _build('Stripe', _wp('stripe') + r'(?=.*(?:payment|api|billing|integration))'),
    _build('Plaid', _wp('plaid') + r'(?=.*(?:api|banking|fintech|financial))'),

    #design tools
    _build('Figma', _wp('figma')),
    _build('Sketch', _wp('sketch') + r'(?=.*(?:design|ui|ux|prototype))'),
    _build('Photoshop', _wp('photoshop')),
    _build('Illustrator', _wp('illustrator')),
    _build('InDesign', _wp('indesign')),
    _build('Adobe XD', _wp('adobe xd')),
    _build('Canva', _wp('canva')),
    _build('Miro', _wp('miro') + r'(?=.*(?:board|whiteboard|design|collaborate))'),

    #engineering and cad
    _build('AutoCAD', _wp('autocad')),
    _build('SolidWorks', _wp('solidworks')),
    _build('Revit', _wp('revit')),
    _build('CATIA', _wp('catia')),
    _build('ArcGIS', _wp('arcgis'), _wp('arc gis')),
    _build('QGIS', _wp('qgis')),

    #methodologies (only specific named ones, not generic terms)
    _build('Agile', _wp('agile')),
    _build('Scrum', _wp('scrum')),
    _build('Kanban', _wp('kanban')),
    _build('CI/CD', _wp('ci/cd'), _wp('ci cd'), r'continuous\s+(?:integration|delivery|deployment)'),
    _build('REST API', _wp('rest api'), _wp('restful'), _wp('rest') + r'(?=.*(?:api|endpoint|service))'),
    _build('GraphQL', _wp('graphql')),
    _build('Microservices', _wp('microservices'), _wp('micro services')),

    #testing
    _build('Selenium', _wp('selenium')),
    _build('Cypress', _wp('cypress')),
    _build('Jest', _wp('jest')),
    _build('pytest', _wp('pytest')),
    _build('JUnit', _wp('junit')),
    _build('Postman', _wp('postman')),

    #mobile
    _build('React Native', _wp('react native')),
    _build('Flutter', _wp('flutter')),
    _build('Xcode', _wp('xcode')),
    _build('Android Studio', _wp('android studio')),

    #security
    _build('OWASP', _wp('owasp')),
    _build('OAuth', _wp('oauth')),
    _build('SAML', _wp('saml')),
    _build('Active Directory', _wp('active directory'), _wp('ad') + r'(?=.*(?:ldap|directory|azure|identity))'),

    #networking
    _build('TCP/IP', _wp('tcp'), _wp('tcp/ip')),
    _build('DNS', _wp('dns')),
    _build('VPN', _wp('vpn')),
    _build('Load Balancing', _wp('load balanc')),

    #finance and accounting specific
    _build('Bloomberg Terminal', _wp('bloomberg')),
    _build('FactSet', _wp('factset')),
    _build('Capital IQ', _wp('capital iq')),
    _build('Hyperion', _wp('hyperion')),
    _build('Netsuite', _wp('netsuite')),
    _build('Power Automate', _wp('power automate')),
    _build('Microsoft Forms', _wp('microsoft forms')),
    _build('SharePoint', _wp('sharepoint')),
    _build('Power Apps', _wp('power apps'), _wp('powerapps')),
    _build('VLookup', _wp('vlookup')),
    _build('Pivot Tables', _wp('pivot table')),
    _build('Macros', _wp('macros') + r'(?=.*(?:excel|vba|spreadsheet|automate))'),
])

#set of canonical names for quick lookup
TAXONOMY_NAMES = frozenset(_TAXONOMY.keys())


def count_taxonomy_skills(descriptions: list[str]) -> Counter:
    #scans all descriptions against the taxonomy using regex
    #returns a counter where each count = number of descriptions mentioning that skill
    #this is the deterministic core — no api calls, no llm, instant
    counts = Counter()
    for desc in descriptions:
        for skill_name, pattern in _TAXONOMY.items():
            if pattern.search(desc):
                counts[skill_name] += 1
    return counts


def count_specific_skills(descriptions: list[str], skill_names: list[str]) -> Counter:
    #counts how many descriptions mention each skill from a custom list
    #used for niche skills discovered by groq that aren't in the taxonomy
    #builds a simple word-boundary regex per skill, case-insensitive
    if not skill_names:
        return Counter()

    patterns = {}
    for name in skill_names:
        try:
            escaped = re.escape(name)
            patterns[name] = re.compile(rf'\b{escaped}\b', re.IGNORECASE)
        except re.error:
            continue

    counts = Counter()
    for desc in descriptions:
        for name, pattern in patterns.items():
            if pattern.search(desc):
                counts[name] += 1

    return counts
