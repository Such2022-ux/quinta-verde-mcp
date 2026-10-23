# Quinta Verde MCP

A private MCP server that exposes limited, read-only tools over the existing Google Apps Script spreadsheet API.

## Deploy on Render

1. Push these files to your **private** GitHub repository.
2. In Render, choose **New + → Web Service** and connect `quinta-verde-mcp`.
3. Render should detect `render.yaml`. Build command: `pip install -r requirements.txt`; start command: `python server.py`.
4. Add these environment variables in Render:
   - `APPS_SCRIPT_URL`: your deployed Apps Script `/exec` URL
   - `APPS_SCRIPT_API_KEY`: your new Script Property API key (never commit it)
   - `MCP_AUTH_TOKEN`: a new long random secret used to protect the MCP endpoint
5. Deploy and check `/health` returns `{"ok":true}`.

## Security notes

- Keep the GitHub repository private.
- Never commit API keys or `.env` files.
- The current Apps Script API returns broad spreadsheet data, so only connect this to a private, trusted ChatGPT plugin.
- The MCP endpoint uses Bearer authentication. Confirm that the eventual ChatGPT plugin connection supports passing this header before connecting.
- This service is read-only. It does not write to Google Sheets.
