"""Atlas — personal job-search automation cockpit engine.

The `engine` package is 100% deterministic Python (no LLM calls). It handles
discovery, scoring, CV rendering, outreach templating, referral matching and the
SQLite store. All LLM *judgment* (nuanced ranking, CV wording, message drafting)
happens in the Claude Cowork scheduled-task session that orchestrates this engine.
"""

__version__ = "0.1.0"
