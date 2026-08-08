# Security boundary

This v0.1 repository is a synthetic-data demonstration only. It has no OAuth, API client, HTTP client, MCP server, LLM client, credential store, or accounting-system write path.

Do not place real Xero exports, client data, tokens, `.env` files, or workpapers in this repository. A future live implementation would require separate access controls, approval, retention, audit, and privacy design; the split between the model result and reviewer evidence files in this demo is **not** a multi-user security boundary.
