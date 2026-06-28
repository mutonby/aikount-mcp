# Dockerfile for Glama (and any container host).
# Glama builds this image, starts the server over stdio and runs an MCP
# introspection request (tools/list). No credentials are needed to list tools
# — AIKOUNT_TOKEN is only required when a tool is actually CALLED — so the
# introspection check passes out of the box.
FROM python:3.12-slim

WORKDIR /app

# Install the package from source.
COPY pyproject.toml README.md LICENSE ./
COPY aikount_mcp ./aikount_mcp
RUN pip install --no-cache-dir .

# stdio MCP server.
ENTRYPOINT ["aikount-mcp"]
