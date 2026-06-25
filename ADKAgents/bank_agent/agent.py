import os
from functools import cached_property

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client

from .observability import (
    after_model_callback,
    before_model_callback,
    setup_observability,
)
from .prompt import ROOT_AGENT_INSTRUCTION, PROFILER_AGENT_INSTRUCTION, PRODUCT_MATCHER_AGENT_INSTRUCTION
from .tools.bigquery_tool import run_bigquery_query
from .tools.customersearch import customer_database_search, customer_id_search
from .tools.productsearch import vertex_vector_search, get_available_products
from .tools.ecommerce_tools import lookup_user_orders, check_product_stock, sales_reporting_query
from google.adk.tools import google_search

load_dotenv()


class VertexGemini(Gemini):
    """Gemini model that unconditionally uses Vertex AI (ADC) instead of an API key."""

    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )


# Initialise OpenTelemetry exporters and the metrics store.
setup_observability()

def search_lloyds_products(query: str) -> str:
    """
    Search Lloyds Bank product pages. https://www.lloydsbank.com/products-and-services.html
    """


# 1. Product Matcher Agent (matches analyzed profile with bank products)
product_matcher_agent = Agent(
    name="product_matcher",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that matches a customer's financial profile with Lloyds Bank's product offerings and recommends products with a summary explaining why.",
    instruction=PRODUCT_MATCHER_AGENT_INSTRUCTION,
    tools=[vertex_vector_search, google_search, get_available_products],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 2. Financial Profiler Agent (analyzes customer's accounts/transactions)
financial_profiler_agent = Agent(
    name="financial_profiler",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that reviews transactions and existing product holdings of the customer to build a holistic financial profile.",
    instruction=PROFILER_AGENT_INSTRUCTION,
    tools=[customer_database_search],
    sub_agents=[product_matcher_agent],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 3. Root Agent (conversation entrypoint, customer verification, general queries)
root_agent = Agent(
    name="bank_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="A helpful banking assistant.",
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[customer_id_search, run_bigquery_query, lookup_user_orders, check_product_stock, sales_reporting_query],
    sub_agents=[financial_profiler_agent],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

