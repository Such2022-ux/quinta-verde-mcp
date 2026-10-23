import os
import json
from typing import Any, Optional
from urllib.parse import urlencode

import requests
import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

APP_SCRIPT_URL = os.environ["APPS_SCRIPT_URL"].strip()
APP_SCRIPT_API_KEY = os.environ["APPS_SCRIPT_API_KEY"].strip()
MCP_AUTH_TOKEN = os.environ["MCP_AUTH_TOKEN"].strip()

if not APP_SCRIPT_URL or not APP_SCRIPT_API_KEY or not MCP_AUTH_TOKEN:
    raise RuntimeError("Set APPS_SCRIPT_URL, APPS_SCRIPT_API_KEY, and MCP_AUTH_TOKEN.")

mcp = FastMCP("Quinta Verde Operations", host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))

def fetch_spreadsheet() -> dict[str, Any]:
    """Fetch current spreadsheet data from the user's existing Apps Script API."""
    response = requests.get(
        APP_SCRIPT_URL,
        params={"key": APP_SCRIPT_API_KEY},
        timeout=45,
        allow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("ok") is False:
        raise RuntimeError("Google Sheets API rejected the request. Check the API key and deployment.")
    return payload

def sheets_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    # Support the response format described for this project and common variants.
    sheets = payload.get("sheets", {})
    if isinstance(sheets, list):
        return {str(item.get("name", f"Sheet {i+1}")): item for i, item in enumerate(sheets) if isinstance(item, dict)}
    if isinstance(sheets, dict):
        return sheets
    return {}

def rows_and_headers(sheet: Any) -> tuple[list[str], list[Any]]:
    if not isinstance(sheet, dict):
        return [], []
    headers = sheet.get("headers", [])
    rows = sheet.get("rows", [])
    return ([str(x) for x in headers] if isinstance(headers, list) else [],
            rows if isinstance(rows, list) else [])

@mcp.tool()
def list_sheets() -> dict[str, Any]:
    """List all current worksheet/tab names and row counts, without returning guest details."""
    payload = fetch_spreadsheet()
    sheets = sheets_from_payload(payload)
    result = []
    for name, sheet in sheets.items():
        headers, rows = rows_and_headers(sheet)
        result.append({"name": name, "row_count": len(rows), "columns": headers})
    return {"updated_at": payload.get("timestamp"), "sheets": result}

@mcp.tool()
def get_sheet_summary(sheet_name: str) -> dict[str, Any]:
    """Return a tab's column names, row count, and a small non-sensitive structural summary. Does not return cell values."""
    payload = fetch_spreadsheet()
    sheets = sheets_from_payload(payload)
    target = next((v for k, v in sheets.items() if str(k).casefold() == sheet_name.casefold()), None)
    if target is None:
        return {"error": "Sheet not found", "available_sheets": list(sheets.keys())}
    headers, rows = rows_and_headers(target)
    return {"sheet": sheet_name, "row_count": len(rows), "columns": headers, "updated_at": payload.get("timestamp")}

@mcp.tool()
def search_sheet_rows(sheet_name: str, search_text: str, limit: int = 10) -> dict[str, Any]:
    """Search a worksheet for matching rows. Returns at most 10 matching rows; use only when the user needs specific records. May return personal data present in the matched row."""
    if not search_text.strip():
        return {"error": "search_text must not be empty"}
    limit = max(1, min(int(limit), 10))
    payload = fetch_spreadsheet()
    sheets = sheets_from_payload(payload)
    target_name = next((k for k in sheets if str(k).casefold() == sheet_name.casefold()), None)
    if target_name is None:
        return {"error": "Sheet not found", "available_sheets": list(sheets.keys())}
    headers, rows = rows_and_headers(sheets[target_name])
    needle = search_text.casefold()
    matches = []
    for row_number, row in enumerate(rows, start=2):
        if isinstance(row, dict):
            values = row
            hit = needle in json.dumps(row, ensure_ascii=False, default=str).casefold()
        elif isinstance(row, list):
            values = {headers[i] if i < len(headers) and headers[i] else f"Column {i+1}": value
                      for i, value in enumerate(row)}
            hit = needle in json.dumps(values, ensure_ascii=False, default=str).casefold()
        else:
            values = {"value": row}
            hit = needle in str(row).casefold()
        if hit:
            matches.append({"row_number": row_number, "values": values})
            if len(matches) >= limit:
                break
    return {"sheet": target_name, "matches": matches, "returned": len(matches), "limit": limit}

@mcp.tool()
def get_sheet_rows(sheet_name: str, start_row: int = 2, limit: int = 10) -> dict[str, Any]:
    """Read a limited range of rows from a worksheet. Row 1 is treated as headers. Maximum 10 rows per call."""
    start_row = max(2, int(start_row))
    limit = max(1, min(int(limit), 10))
    payload = fetch_spreadsheet()
    sheets = sheets_from_payload(payload)
    target_name = next((k for k in sheets if str(k).casefold() == sheet_name.casefold()), None)
    if target_name is None:
        return {"error": "Sheet not found", "available_sheets": list(sheets.keys())}
    headers, rows = rows_and_headers(sheets[target_name])
    offset = start_row - 2
    chosen = rows[offset:offset + limit]
    output = []
    for row_number, row in enumerate(chosen, start=start_row):
        if isinstance(row, dict):
            values = row
        elif isinstance(row, list):
            values = {headers[i] if i < len(headers) and headers[i] else f"Column {i+1}": value
                      for i, value in enumerate(row)}
        else:
            values = {"value": row}
        output.append({"row_number": row_number, "values": values})
    return {"sheet": target_name, "columns": headers, "rows": output, "returned": len(output)}

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Health checks are public; MCP traffic must carry the secret bearer token.
        if request.url.path in ("/", "/health"):
            return await call_next(request)
        supplied = request.headers.get("authorization", "")
        if supplied != f"Bearer {MCP_AUTH_TOKEN}":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

@mcp.custom_route("/", methods=["GET"])
async def root(request):
    return JSONResponse({"service": "Quinta Verde MCP", "status": "running"})

@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"ok": True})

if __name__ == "__main__":
    app = mcp.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
