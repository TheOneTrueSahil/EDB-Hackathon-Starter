from google.cloud import discoveryengine_v1 as discoveryengine
from google.adk.tools.tool_context import ToolContext
from ..observability.tool_tracer import traced_tool

# Define your Datastore specifics
PROJECT_ID = "edb-hack2026-team9"
LOCATION = "global"
DATASTORE_ID = "team9ragdatastore_1782469419545"

@traced_tool
def vector_search_tool(query: str, tool_context: ToolContext) -> str:
    """
    Searches the RAG database for successful existing LBG Customer and Product Holdings 
    to recommend Lloyds Bank product offerings.
    
    Args:
        query: The customer profile details or customer ID to search for.
    """
    try:
        # Initialize the Discovery Engine Client
        client = discoveryengine.SearchServiceClient()
        serving_config = client.serving_config_path(
            project=PROJECT_ID,
            location=LOCATION,
            data_store=DATASTORE_ID,
            serving_config="default_config",
        )

        # Execute the search
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=5, # Limit results
        )
        response = client.search(request)

        # Parse the results into a string for the LLM
        results = []
        for result in response.results:
            # Adjust 'document.derived_struct_data' based on your actual Vertex AI schema
            results.append(str(result.document.derived_struct_data))
            
        if not results:
            return "No matching successful customer profiles found."
            
        return "\n---\n".join(results)

    except Exception as e:
        return f"Vertex Search Error: {str(e)}"