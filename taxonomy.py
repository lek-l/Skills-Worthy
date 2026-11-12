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
    _build('Go', _wp('golang')),    
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

    #accounting and finance
    _build('GAAP', _wp('gaap'), _wp('generally accepted accounting')),
    _build('IFRS', _wp('ifrs'), _wp('international financial reporting')),
    _build('CPA', _wp('cpa') + r'(?=.*(?:certified|accounting|audit|finance))'),
    _build('SOX', _wp('sox'), _wp('sarbanes')),
    _build('Accounts Payable', _wp('accounts payable'), _wp('a/p'), _wp('ap') + r'(?=.*(?:invoice|payable|vendor))'),
    _build('Accounts Receivable', _wp('accounts receivable'), _wp('a/r'), _wp('ar') + r'(?=.*(?:invoice|receivable|billing))'),
    _build('General Ledger', _wp('general ledger'), _wp('g/l'), _wp('gl') + r'(?=.*(?:ledger|accounting|journal))'),
    _build('Financial Modeling', _wp('financial model')),
    _build('NetSuite', _wp('netsuite')),
    _build('Sage', _wp('sage') + r'(?=.*(?:accounting|erp|software|intacct|50|100|200|300))'),
    _build('Sage Intacct', _wp('intacct')),
    _build('ADP', _wp('adp') + r'(?=.*(?:payroll|workforce|hr|human))'),
    _build('Concur', _wp('concur') + r'(?=.*(?:expense|travel|sap))'),
    _build('Bill.com', _wp('bill.com')),
    _build('Coupa', _wp('coupa')),
    _build('Anaplan', _wp('anaplan')),
    _build('Adaptive Planning', _wp('adaptive planning'), _wp('adaptive insights')),
    _build('ERP', _wp('erp')),
    _build('Accounts Reconciliation', _wp('reconciliation') + r'(?=.*(?:account|bank|balance|ledger))'),
    _build('Budgeting', _wp('budgeting') + r'(?=.*(?:forecast|financial|planning|annual))'),
    _build('Auditing', _wp('audit') + r'(?=.*(?:internal|external|financial|compliance|sox))'),
    _build('Tax Preparation', _wp('tax preparation'), _wp('tax return'), _wp('tax filing')),
    _build('Cost Accounting', _wp('cost accounting')),
    _build('Payroll', _wp('payroll') + r'(?=.*(?:processing|management|system|adp|software))'),
    _build('Invoice Processing', _wp('invoice') + r'(?=.*(?:processing|management|automation))'),
    _build('10-K', _wp('10-k'), _wp('10k') + r'(?=.*(?:filing|sec|report|annual))'),
    _build('10-Q', _wp('10-q'), _wp('10q') + r'(?=.*(?:filing|sec|report|quarterly))'),

    #marketing and digital
    _build('SEO', _wp('seo'), _wp('search engine optimization')),
    _build('SEM', _wp('sem'), _wp('search engine marketing')),
    _build('Google Ads', _wp('google ads'), _wp('adwords'), _wp('google adwords')),
    _build('Meta Ads', _wp('meta ads'), _wp('facebook ads'), _wp('instagram ads')),
    _build('LinkedIn Ads', _wp('linkedin ads')),
    _build('Mailchimp', _wp('mailchimp')),
    _build('Marketo', _wp('marketo')),
    _build('Hootsuite', _wp('hootsuite')),
    _build('Buffer', _wp('buffer') + r'(?=.*(?:social|media|schedule|marketing))'),
    _build('Sprout Social', _wp('sprout social')),
    _build('Google Tag Manager', _wp('google tag manager'), _wp('gtm') + r'(?=.*(?:tag|tracking|google|analytics))'),
    _build('Segment', _wp('segment') + r'(?=.*(?:analytics|data|tracking|cdp))'),
    _build('Hotjar', _wp('hotjar')),
    _build('Optimizely', _wp('optimizely')),
    _build('A/B Testing', _wp('a/b test'), _wp('ab test'), _wp('split test')),
    _build('CMS', _wp('cms') + r'(?=.*(?:content|management|wordpress|drupal))'),
    _build('WordPress', _wp('wordpress')),
    _build('Drupal', _wp('drupal')),
    _build('Shopify', _wp('shopify')),
    _build('Magento', _wp('magento')),
    _build('Adobe Analytics', _wp('adobe analytics'), _wp('omniture')),
    _build('Klaviyo', _wp('klaviyo')),
    _build('Braze', _wp('braze')),
    _build('Pardot', _wp('pardot')),
    _build('Moz', _wp('moz') + r'(?=.*(?:seo|keyword|rank|backlink))'),
    _build('Ahrefs', _wp('ahrefs')),
    _build('SEMrush', _wp('semrush')),
    _build('Content Marketing', _wp('content marketing'), _wp('content strategy')),
    _build('Email Marketing', _wp('email marketing'), _wp('email campaign')),
    _build('Social Media Marketing', _wp('social media marketing'), _wp('smm')),
    _build('Conversion Rate Optimization', _wp('conversion rate optimization'), _wp('cro') + r'(?=.*(?:conversion|optimization|funnel))'),
    _build('Google Search Console', _wp('google search console'), _wp('search console')),
    _build('Webflow', _wp('webflow')),

    #healthcare and clinical
    _build('Epic', _wp('epic') + r'(?=.*(?:ehr|emr|health|clinical|medical|hospital|electronic))'),
    _build('Cerner', _wp('cerner')),
    _build('HIPAA', _wp('hipaa')),
    _build('HL7', _wp('hl7')),
    _build('FHIR', _wp('fhir')),
    _build('ICD-10', _wp('icd'), _wp('icd-10')),
    _build('CPT Codes', _wp('cpt') + r'(?=.*(?:code|billing|medical|procedure))'),
    _build('Electronic Health Records', _wp('ehr'), _wp('emr'), _wp('electronic health record'), _wp('electronic medical record')),
    _build('Clinical Trials', _wp('clinical trial')),
    _build('MEDITECH', _wp('meditech')),
    _build('Allscripts', _wp('allscripts')),
    _build('Athenahealth', _wp('athenahealth'), _wp('athena health')),
    _build('Medical Billing', _wp('medical billing'), _wp('medical coding')),
    _build('LIMS', _wp('lims') + r'(?=.*(?:laboratory|lab|information|management))'),
    _build('SAS Clinical', _wp('sas') + r'(?=.*(?:clinical|pharma|fda|cdisc))'),
    _build('CDISC', _wp('cdisc')),
    _build('REDCap', _wp('redcap')),
    _build('FDA Regulations', _wp('fda') + r'(?=.*(?:regulation|compliance|approval|submission|guideline))'),

    #legal
    _build('Westlaw', _wp('westlaw')),
    _build('LexisNexis', _wp('lexisnexis'), _wp('lexis nexis'), _wp('lexis')),
    _build('eDiscovery', _wp('ediscovery'), _wp('e-discovery')),
    _build('Contract Management', _wp('contract management'), _wp('contract lifecycle')),
    _build('Legal Research', _wp('legal research')),
    _build('Relativity', _wp('relativity') + r'(?=.*(?:ediscovery|legal|review|litigation))'),
    _build('iManage', _wp('imanage')),
    _build('Clio', _wp('clio') + r'(?=.*(?:legal|law|practice|management))'),
    _build('DocuSign', _wp('docusign')),
    _build('Adobe Sign', _wp('adobe sign')),
    _build('Compliance', _wp('compliance') + r'(?=.*(?:regulatory|legal|audit|risk|officer|program))'),
    _build('GDPR', _wp('gdpr')),
    _build('CCPA', _wp('ccpa')),

    #supply chain and operations
    _build('SAP MM', _wp('sap mm'), _wp('sap') + r'(?=.*(?:materials management|mm module))'),
    _build('Oracle SCM', _wp('oracle scm'), _wp('oracle') + r'(?=.*(?:supply chain|scm))'),
    _build('Demand Planning', _wp('demand planning'), _wp('demand forecast')),
    _build('Inventory Management', _wp('inventory management')),
    _build('Six Sigma', _wp('six sigma'), _wp('6 sigma'), _wp('lean six sigma')),
    _build('Lean', _wp('lean') + r'(?=.*(?:manufacturing|methodology|six sigma|process|kaizen))'),
    _build('Kaizen', _wp('kaizen')),
    _build('WMS', _wp('wms') + r'(?=.*(?:warehouse|management|system|inventory))'),
    _build('MRP', _wp('mrp') + r'(?=.*(?:material|resource|planning|manufacturing))'),
    _build('Procurement', _wp('procurement') + r'(?=.*(?:software|system|management|strategic|sourcing))'),
    _build('Logistics', _wp('logistics') + r'(?=.*(?:management|software|supply|chain|warehouse))'),
    _build('TMS', _wp('tms') + r'(?=.*(?:transport|management|system|freight))'),

    #hr and recruiting
    _build('BambooHR', _wp('bamboohr'), _wp('bamboo hr')),
    _build('Greenhouse', _wp('greenhouse') + r'(?=.*(?:recruit|hiring|ats|applicant|talent))'),
    _build('Lever', _wp('lever') + r'(?=.*(?:recruit|hiring|ats|applicant|talent))'),
    _build('iCIMS', _wp('icims')),
    _build('Taleo', _wp('taleo')),
    _build('SuccessFactors', _wp('successfactors'), _wp('success factors')),
    _build('UltiPro', _wp('ultipro'), _wp('ukg') + r'(?=.*(?:payroll|hr|workforce|human))'),
    _build('Kronos', _wp('kronos') + r'(?=.*(?:workforce|timekeeping|hr|payroll))'),
    _build('Applicant Tracking', _wp('applicant tracking'), _wp('ats') + r'(?=.*(?:system|recruiting|hiring|applicant))'),
    _build('HRIS', _wp('hris')),
    _build('PeopleSoft', _wp('peoplesoft')),
    _build('Ceridian', _wp('ceridian'), _wp('dayforce')),
    _build('Gusto', _wp('gusto') + r'(?=.*(?:payroll|hr|benefits|software))'),
    _build('Rippling', _wp('rippling')),
    _build('Deel', _wp('deel') + r'(?=.*(?:payroll|hr|global|remote|compliance))'),

    #project management
    _build('MS Project', _wp('ms project'), _wp('microsoft project')),
    _build('Smartsheet', _wp('smartsheet')),
    _build('Basecamp', _wp('basecamp')),
    _build('Wrike', _wp('wrike')),
    _build('Airtable', _wp('airtable')),
    _build('ClickUp', _wp('clickup')),
    _build('PMP', _wp('pmp') + r'(?=.*(?:certified|certification|project|management))'),
    _build('PRINCE2', _wp('prince2')),
    _build('Waterfall', _wp('waterfall') + r'(?=.*(?:methodology|project|sdlc|development))'),
    _build('ITIL', _wp('itil')),

    #communication and collaboration
    _build('Microsoft Teams', _wp('microsoft teams'), _wp('ms teams')),
    _build('Zoom', _wp('zoom') + r'(?=.*(?:meeting|video|call|conference|webinar))'),
    _build('Webex', _wp('webex')),

    #business intelligence and reporting
    _build('Crystal Reports', _wp('crystal reports')),
    _build('Cognos', _wp('cognos')),
    _build('MicroStrategy', _wp('microstrategy')),
    _build('SAP BusinessObjects', _wp('businessobjects'), _wp('business objects')),
    _build('Domo', _wp('domo') + r'(?=.*(?:dashboard|analytics|bi|data|reporting))'),
    _build('Sisense', _wp('sisense')),
    _build('Mode Analytics', _wp('mode analytics'), _wp('mode') + r'(?=.*(?:analytics|sql|dashboard|bi))'),
    _build('Metabase', _wp('metabase')),
    _build('Apache Superset', _wp('superset')),

    #real estate and construction
    _build('Yardi', _wp('yardi')),
    _build('MRI Software', _wp('mri software'), _wp('mri') + r'(?=.*(?:real estate|property|management))'),
    _build('CoStar', _wp('costar')),
    _build('Procore', _wp('procore')),
    _build('Bluebeam', _wp('bluebeam')),
    _build('PlanGrid', _wp('plangrid')),

    #education
    _build('Canvas LMS', _wp('canvas') + r'(?=.*(?:lms|learning|course|education))'),
    _build('Blackboard', _wp('blackboard')),
    _build('Moodle', _wp('moodle')),
    _build('Google Classroom', _wp('google classroom')),
    _build('Schoology', _wp('schoology')),

    #data governance and quality
    _build('Collibra', _wp('collibra')),
    _build('Alation', _wp('alation')),
    _build('Atlan', _wp('atlan') + r'(?=.*(?:data|catalog|governance|metadata))'),
    _build('Great Expectations', _wp('great expectations') + r'(?=.*(?:data|quality|validation|test))'),
    _build('Monte Carlo', _wp('monte carlo') + r'(?=.*(?:data|observability|quality|reliability))'),
    _build('Data Governance', _wp('data governance')),
    _build('Master Data Management', _wp('master data management'), _wp('mdm') + r'(?=.*(?:data|master|management))'),
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