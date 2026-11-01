
def sheets_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize the Apps Script response into the format used by the MCP tools."""

    # Handle the actual Apps Script response:
    # {"success": true, "lastUpdated": "...", "count": 365, "data": [...]}
    data = payload.get("data")

    if isinstance(data, list):
        headers = list(data[0].keys()) if data and isinstance(data[0], dict) else []
        return {
            "Room Pricing": {
                "headers": headers,
                "rows": data,
            }
        }

    # Retain support for the previous API response format.
    sheets = payload.get("sheets", {})

    if isinstance(sheets, list):
        return {
            str(item.get("name", f"Sheet {i + 1}")): item
            for i, item in enumerate(sheets)
            if isinstance(item, dict)
        }

    if isinstance(sheets, dict):
        return sheets

    return {}
