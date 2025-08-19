BIB_FILENAME = "library.bib"

# Metadata extraction
USE_GROBID = False
GROBID_URL = "http://localhost:8070/api/processHeaderDocument"

# Crossref
USER_AGENT = "ref-sync/0.1 (mailto:you@example.com)"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"
# Semantic Scholar
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
# OpenAlex
OPENALEX_URL = "https://api.openalex.org/works"

DOI_CONTENT_NEGOTIATION_URL = "https://doi.org/{doi}"
