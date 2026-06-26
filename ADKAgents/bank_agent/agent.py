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
    PRODUCT_MATCHER_AGENT_INSTRUCTION,
    SPENDING_INSIGHTS_AGENT_INSTRUCTION,
    GOAL_AGENT_INSTRUCTION,
    NON_SAVINGS_GOAL_PROFILER_AGENT_INSTRUCTION,
    SAVINGS_GOAL_PROFILER_AGENT_INSTRUCTION,
    GOAL_SPENDING_INSIGHTS_AGENT_INSTRUCTION,
    SAVINGS_GOAL_PRODUCT_MATCHER_AGENT_INSTRUCTION,
)
from .tools.bigquery_tool import run_bigquery_query
from .tools.customersearch import customer_database_search, customer_id_search
from .tools.productsearch import get_available_products
from .tools.ecommerce_tools import lookup_user_orders, check_product_stock, sales_reporting_query

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
product_matcher_agent = Agent(
    name="product_matcher",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that matches a customer's financial profile with Lloyds Bank's product offerings and recommends products with a summary explaining why.",
    instruction=PRODUCT_MATCHER_AGENT_INSTRUCTION,
    tools=[get_available_products],
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

# 3. Spending Insights Agent (analyzes category spending and comparisons)
spending_insights_agent = Agent(
    name="spending_insights",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that analyzes category spending, compares it against the previous month, and offers one key recommendation to improve spending habits.",
    instruction=SPENDING_INSIGHTS_AGENT_INSTRUCTION,
    tools=[customer_database_search],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 4. Non-Savings Goal Product Matcher Agent
non_savings_goal_product_matcher_agent = Agent(
    name="non_savings_goal_product_matcher",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that matches a customer's financial profile and goals with Lloyds Bank's product offerings.",
    instruction=PRODUCT_MATCHER_AGENT_INSTRUCTION,
    tools=[get_available_products],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 5. Non-Savings Goal Profiler Agent
non_savings_goal_profiler_agent = Agent(
    name="non_savings_goal_profiler",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that reviews transactions and holdings specifically to analyze capability for non-savings goals.",
    instruction=NON_SAVINGS_GOAL_PROFILER_AGENT_INSTRUCTION,
    tools=[customer_database_search],
    sub_agents=[non_savings_goal_product_matcher_agent],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 6. Savings Goal Product Matcher Agent
savings_goal_product_matcher_agent = Agent(
    name="savings_goal_product_matcher",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that matches a customer's financial profile, spending habits, and savings goals with Lloyds Bank's products.",
    instruction=SAVINGS_GOAL_PRODUCT_MATCHER_AGENT_INSTRUCTION,
    tools=[get_available_products],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 7. Savings Goal Profiler Agent
savings_goal_profiler_agent = Agent(
    name="savings_goal_profiler",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that reviews transactions and holdings specifically to analyze capability and optimize savings goals.",
    instruction=SAVINGS_GOAL_PROFILER_AGENT_INSTRUCTION,
    tools=[customer_database_search],
    sub_agents=[savings_goal_product_matcher_agent],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 8. Goal Spending Insights Agent (reviews spending to help optimize savings goals)
goal_spending_insights_agent = Agent(
    name="goal_spending_insights",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that analyzes category spending to help optimize the customer's savings strategy.",
    instruction=GOAL_SPENDING_INSIGHTS_AGENT_INSTRUCTION,
    tools=[customer_database_search],
    sub_agents=[savings_goal_profiler_agent],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 9. Goal Agent (assists with financial goals and coordinates with the profiler and spending insights)
goal_agent = Agent(
    name="goal",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="An agent that helps the user set and plan for financial goals, coordinating with the financial profiler and spending insights agent to ensure recommendations suit their profile and optimize their savings strategy.",
    instruction=GOAL_AGENT_INSTRUCTION,
    sub_agents=[non_savings_goal_profiler_agent, goal_spending_insights_agent],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

# 10. Root Agent (conversation entrypoint, customer verification, general queries)
root_agent = Agent(
    name="bank_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="A helpful banking assistant.",
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[customer_id_search, run_bigquery_query, lookup_user_orders, check_product_stock, sales_reporting_query],
    sub_agents=[financial_profiler_agent, spending_insights_agent, goal_agent],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)

