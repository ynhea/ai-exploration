from mcp.server.fastmcp import FastMCP
from tool_utils import calculate_annual_leave, search_company_docs

# mcp 서버 객체 생성
mcp = FastMCP("compasslab-tools")

# 계산 Tool
mcp.tool()(calculate_annual_leave)

# 검색 Tool
mcp.tool()(search_company_docs)


if __name__ == "__main__":
    mcp.run() 