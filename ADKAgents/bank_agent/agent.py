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
from .prompt import (
    ROOT_AGENT_INSTRUCTION,
    PROFILER_AGENT_INSTRUCTION,
    RECOMMENDATION_AGENT_INSTRUCTION,
    PRODUCT_MATCHER_AGENT_INSTRUCTION,
    SPENDING_INSIGHTS_AGENT_INSTRUCTION,
    GOAL_AGENT_INSTRUCTION,
)

from .tools.bigquery_tool import run_bigquery_query
from .tools.customersearch import customer_database_search, customer_id_search
from .tools.productsearch import get_available_products
from .tools.ecommerce_tools import lookup_user_orders, check_product_stock, sales_reporting_query
# from google.adk.tools import google_search
from .tools.vector_search_tool import vector_search_tool

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

# 1. Product Matcher Agent (matches analyzed profile with bank products)
recommendation_agent = Agent(
    name="recommendation_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that matches a customer's financial profile with a RAG DB of successful existing LBG Customer and Product Holding , to recommend Lloyds Bank's product offerings and recommends products with a summary explaining why.",
    instruction=RECOMMENDATION_AGENT_INSTRUCTION,
    tools=[vector_search_tool],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)


# 1. Product Matcher Agent (matches analyzed profile with bank products)
product_matcher_agent = Agent(
    name="product_matcher",
    model=VertexGemini(model="gemini-3.1-pro-preview"),
    description="An agent that matches a customer's financial profile with Lloyds Bank's product offerings and recommends products with a summary explaining why.",
    instruction=PRODUCT_MATCHER_AGENT_INSTRUCTION,
    tools=[get_available_products],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 2. Financial Profiler Agent (analyzes customer's accounts/transactions)
financial_profiler_agent = Agent(
    name="financial_profiler",
    model=VertexGemini(model="gemini-3.1-pro-preview"),
    description="An agent that reviews transactions and existing product holdings of the customer to build a holistic financial profile.",
    instruction=PROFILER_AGENT_INSTRUCTION,
    tools=[customer_database_search],
    sub_agents=[product_matcher_agent],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 1.5 Spending Insights Agent (analyzes category spending and comparisons)
spending_insights_agent = Agent(
    name="spending_insights",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that analyzes category spending, compares it against the previous month, and offers one key recommendation to improve spending habits.",
    instruction=SPENDING_INSIGHTS_AGENT_INSTRUCTION,
    tools=[customer_database_search],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 1.6 Goal Agent (assists with financial goals and coordinates with the profiler and spending insights agent)
goal_agent = Agent(
    name="goal",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that helps the user set and plan for financial goals, coordinating with the financial profiler and spending insights agent to ensure recommendations suit their profile and optimize their savings strategy.",
    instruction=GOAL_AGENT_INSTRUCTION,
    sub_agents=[financial_profiler_agent, spending_insights_agent],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 3. Root Agent (conversation entrypoint, customer verification, general queries)
root_agent = Agent(
    name="bank_agent",
    model=VertexGemini(model="gemini-3.1-pro-preview"),
    description="A helpful banking assistant.",
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[customer_id_search, run_bigquery_query, lookup_user_orders, check_product_stock, sales_reporting_query],
    sub_agents=[financial_profiler_agent, spending_insights_agent, goal_agent,recommendation_agent],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

