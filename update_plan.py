import re

with open("docs/superpowers/plans/2026-04-12-strict-graph-ingestion.md", "r") as f:
    plan = f.read()

# Replace docstrings in the plan with 5-year-old language
docstrings = {
    '"""Represents one entity mention extracted from one chunk before deduplication."""': '"""This tells us about one name or thing we found in a small piece of text, before we check if we already found it before."""',
    '"""Represents one strict-schema relationship extracted from one chunk."""': '"""This shows how two names or things are connected to each other in a piece of text, using only the connections we allow."""',
    '"""Returns the canonical relationship schema text used in every extraction prompt."""': '"""This gives us the exact list of allowed connections as text, so we can tell the AI exactly what words to use when connecting things."""',
    '"""Extracts raw entities and strict-schema relationships from one chunk."""': '"""This function looks at a small piece of the text and asks the AI to find all the important names (like people or places) and how they connect to each other, like drawing lines between dots."""',
    '"""Builds the extraction prompt for one chunk using the shared relationship schema."""': '"""This function puts together the instructions and the text piece so we can ask the AI to find names and connections."""',
    '"""Generates embeddings for many texts in one API call."""': '"""This turns a list of words into a list of numbers all at once. These numbers help us understand what the words mean so we can find similar words later."""',
    '"""Groups names by a simple normalized key for exact deduplication."""': '"""This function puts names that look exactly the same (except for capital letters or extra spaces) into groups, so we know they are the same thing."""',
    '"""Returns fuzzy-match pairs that are likely the same entity."""': '"""This function finds pairs of names that look very similar, like "Apple" and "Apple Inc", and puts them together so we can check if they mean the same thing."""',
    '"""Represents one unresolved entity pair that needs final LLM review."""': '"""This holds two names that look a bit similar but we are not completely sure if they are the same thing, so we need to ask the AI to decide."""',
    '"""Represents one final decision returned by the cleanup LLM call."""': '"""This is the final answer from the AI about whether two names mean the same thing, and what the best name to use for both of them is."""',
    '"""Asks the LLM to merge or split only the ambiguous entity pairs."""': '"""This function asks the AI to look at pairs of names we are confused about, and decide if they are the same thing or different things."""',
    '"""Rewrites raw entity names to canonical names before Neo4j persistence."""': '"""This function takes all the names we found and changes them to the single best name we chose for them, so we can save them correctly."""',
    '"""Collapses duplicate relationships while keeping evidence and chunk provenance."""': '"""This function takes many identical connections and squishes them into one, making sure we remember all the places we found them."""',
    '"""Upserts one document node."""': '"""This saves the main document file name into our database so we can link everything back to it."""',
    '"""Writes canonical entities, mentions, and strict-schema relationships to Neo4j."""': '"""This function saves all the best names and how they connect into our graph database, so we can search through them later."""',
    '"""Runs the full graph ingestion pipeline for one document."""': '"""This is the big boss function. It takes one document, breaks it into pieces, finds names and connections in each piece, cleans up the names so there are no duplicates, and saves everything into the database."""',
    '"""Handles the HTTP request and delegates to the graph ingestion coordinator."""': '"""This gets the request from the web when someone wants to process a document, and hands it over to the big boss function to do the work."""'
}

for old, new in docstrings.items():
    plan = plan.replace(old, new)

# Add docstrings to test functions
test_docstrings = {
    'def test_relationship_schema_prompt_lists_every_allowed_relationship():': 'def test_relationship_schema_prompt_lists_every_allowed_relationship():\n    """This test checks to make sure every connection type we allow is written down in the instructions we give to the AI."""',
    'def test_raw_graph_relationship_rejects_unknown_relationship_type():': 'def test_raw_graph_relationship_rejects_unknown_relationship_type():\n    """This test makes sure that if the AI tries to use a connection type we did not allow, we throw an error and stop it."""',
    'def test_parse_chunk_graph_extraction_response_returns_entities_and_relationships():': 'def test_parse_chunk_graph_extraction_response_returns_entities_and_relationships():\n    """This test checks if we can correctly understand the answer the AI gives us and pull out the names and connections from it."""',
    'def test_group_entities_by_normalized_name_merges_case_only_differences():': 'def test_group_entities_by_normalized_name_merges_case_only_differences():\n    """This test makes sure that when we have the same name written with different capital letters, we group them as the exact same name."""',
    'def test_find_fuzzy_merge_candidates_detects_company_suffix_variants():': 'def test_find_fuzzy_merge_candidates_detects_company_suffix_variants():\n    """This test makes sure we can find and group names that look very similar, like a company name with or without the word \'Inc\'."""',
    'def test_split_clear_cases_from_ambiguous_cases_keeps_mid_band_for_later_resolution():': 'def test_split_clear_cases_from_ambiguous_cases_keeps_mid_band_for_later_resolution():\n    """This test checks that we can correctly separate the pairs of names that are super obvious from the pairs that are confusing and need the AI to look at them."""',
    'def test_build_entity_resolution_review_payload_only_contains_ambiguous_cases():': 'def test_build_entity_resolution_review_payload_only_contains_ambiguous_cases():\n    """This test makes sure we only send the confusing pairs of names to the AI for review, and not the obvious ones."""',
    'def test_rewrite_graph_results_to_canonical_entities_updates_relationship_endpoints():': 'def test_rewrite_graph_results_to_canonical_entities_updates_relationship_endpoints():\n    """This test checks that when we change a name to its best version, we also update all the connections that use that name to point to the new best version."""',
    'def test_build_neo4j_graph_write_payload_contains_mentions_and_relationships():': 'def test_build_neo4j_graph_write_payload_contains_mentions_and_relationships():\n    """This test makes sure that the package of data we send to the database contains all the names, where they were mentioned, and how they connect."""',
    'def test_ingest_document_graph_runs_all_pipeline_stages(monkeypatch):': 'def test_ingest_document_graph_runs_all_pipeline_stages(monkeypatch):\n    """This test watches the big boss function to make sure it runs all the required steps in the right order without skipping anything."""'
}

for old, new in test_docstrings.items():
    plan = plan.replace(old, new)


# Write back
with open("docs/superpowers/plans/2026-04-12-strict-graph-ingestion.md", "w") as f:
    f.write(plan)
