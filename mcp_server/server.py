"""DEPRECATED — this module has been replaced by services.it_ops_api.main.

Importing or running it now raises an error. Run the new ops API with:

    uvicorn services.it_ops_api.main:app --port 8001 --reload
"""

raise RuntimeError(
    "mcp_server.server is deprecated. Use services.it_ops_api.main instead."
)
