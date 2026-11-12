import os

#dummy keys so modules that build clients at import time can load
#no test makes a real network call, every external call is mocked
os.environ["GROQ_API_KEY"] = "test-groq-key"
os.environ["JSEARCH_API_KEY"] = "test-jsearch-key"
