"""Wires the agents into the LangGraph pipeline:

    parse_request -> scrape_site (one per site, parallel) -> collect
        -> price | condition | value (parallel, new vehicles) -> rank ----+
        -> check_availability (vehicles sent before) --------------------+-> send_email
"""
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents.availability import check_availability
from app.agents.collect import collect
from app.agents.condition import condition
from app.agents.parse_request import parse_request
from app.agents.price import price
from app.agents.rank import rank
from app.agents.scraper import scrape_site
from app.agents.send_email import send_email
from app.agents.state import PipelineState
from app.agents.value import value


def fan_out_sites(state: PipelineState) -> list[Send]:
    return [Send("scrape_site", {"site": site, "criteria": state["criteria"]}) for site in state["sites"]]


def build_graph():
    g = StateGraph(PipelineState)

    g.add_node("parse_request", parse_request)
    g.add_node("scrape_site", scrape_site)
    g.add_node("collect", collect)
    g.add_node("price", price)
    g.add_node("condition", condition)
    g.add_node("value", value)
    g.add_node("rank", rank)
    g.add_node("check_availability", check_availability)
    g.add_node("send_email", send_email)

    g.add_edge(START, "parse_request")
    g.add_conditional_edges("parse_request", fan_out_sites, ["scrape_site"])
    g.add_edge("scrape_site", "collect")
    for analyst in ("price", "condition", "value"):
        g.add_edge("collect", analyst)
    g.add_edge(["price", "condition", "value"], "rank")  # waits for all three
    g.add_edge("collect", "check_availability")
    g.add_edge(["rank", "check_availability"], "send_email")  # waits for both
    g.add_edge("send_email", END)

    return g.compile()


graph = build_graph()
