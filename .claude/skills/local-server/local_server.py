"""
Local FastAPI server for running agentic directives.
Same code as Modal, but runs on your laptop.

Run: uvicorn execution.local_server:app --reload --port 8000
Expose: ngrok http 8000

Endpoints:
  GET  /               - Server info
  POST /webhook/{slug} - Execute directive by slug
  GET  /webhooks       - List available webhooks
"""

import os
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("local-orchestrator")

app = FastAPI(title="Claude Orchestrator (Local)", version="1.0")

# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================

def send_email_impl(to: str, subject: str, body: str) -> dict:
    """Send email via Gmail API."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    from email.mime.text import MIMEText
    import base64

    # Load token
    token_path = Path("token.json")
    if not token_path.exists():
        return {"error": "token.json not found"}

    token_data = json.loads(token_path.read_text())

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data["scopes"]
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build("gmail", "v1", credentials=creds)
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    logger.info(f"📧 Email sent to {to} | ID: {result['id']}")
    return {"status": "sent", "message_id": result["id"]}


def read_sheet_impl(spreadsheet_id: str, range: str) -> dict:
    """Read from Google Sheet."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request

    token_path = Path("token.json")
    if not token_path.exists():
        return {"error": "token.json not found"}

    token_data = json.loads(token_path.read_text())

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data["scopes"]
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build("sheets", "v4", credentials=creds)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range
    ).execute()

    values = result.get("values", [])
    logger.info(f"📊 Read {len(values)} rows from sheet")
    return {"rows": len(values), "values": values}


def update_sheet_impl(spreadsheet_id: str, range: str, values: list) -> dict:
    """Update Google Sheet."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request

    token_path = Path("token.json")
    if not token_path.exists():
        return {"error": "token.json not found"}

    token_data = json.loads(token_path.read_text())

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data["scopes"]
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build("sheets", "v4", credentials=creds)
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range,
        valueInputOption="USER_ENTERED",
        body={"values": values}
    ).execute()

    logger.info(f"📊 Updated {result.get('updatedCells', 0)} cells")
    return {"updated_cells": result.get("updatedCells", 0)}


# Map tool names to implementations
TOOL_IMPLEMENTATIONS = {
    "send_email": lambda **kwargs: send_email_impl(**kwargs),
    "read_sheet": lambda **kwargs: read_sheet_impl(**kwargs),
    "update_sheet": lambda **kwargs: update_sheet_impl(**kwargs),
}

# Tool definitions for Claude
ALL_TOOLS = {
    "send_email": {
        "name": "send_email",
        "description": "Send an email via Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body content"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    "read_sheet": {
        "name": "read_sheet",
        "description": "Read data from a Google Sheet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string", "description": "The Google Sheet ID"},
                "range": {"type": "string", "description": "A1 notation range"}
            },
            "required": ["spreadsheet_id", "range"]
        }
    },
    "update_sheet": {
        "name": "update_sheet",
        "description": "Update cells in a Google Sheet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string", "description": "The Google Sheet ID"},
                "range": {"type": "string", "description": "A1 notation range"},
                "values": {"type": "array", "description": "2D array of values"}
            },
            "required": ["spreadsheet_id", "range", "values"]
        }
    },
}

# ============================================================================
# SCRIPT EXECUTION
# ============================================================================

SCRIPT_HANDLERS = {}

def run_upwork_scrape_apply(input_data: dict) -> dict:
    """Run the Upwork scrape and apply pipeline."""
    limit = input_data.get("limit", 50)
    days = input_data.get("days", 1)
    workers = input_data.get("workers", 5)
    keywords = input_data.get("keywords", None)

    results = {"steps": [], "errors": []}

    # Step 1: Scrape jobs
    logger.info(f"📡 Scraping Upwork jobs (limit={limit}, days={days})")
    scrape_cmd = [
        sys.executable, "execution/upwork_apify_scraper.py",
        "--limit", str(limit),
        "--days", str(days),
        "-o", ".tmp/upwork_jobs_batch.json"
    ]
    if input_data.get("verified_payment"):
        scrape_cmd.append("--verified-payment")

    try:
        scrape_result = subprocess.run(
            scrape_cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(Path(__file__).parent.parent)
        )
        results["steps"].append({
            "step": "scrape",
            "returncode": scrape_result.returncode,
            "stdout": scrape_result.stdout[-2000:] if scrape_result.stdout else "",
            "stderr": scrape_result.stderr[-1000:] if scrape_result.stderr else ""
        })
        if scrape_result.returncode != 0:
            results["errors"].append(f"Scrape failed: {scrape_result.stderr}")
            return results
    except subprocess.TimeoutExpired:
        results["errors"].append("Scrape timed out after 5 minutes")
        return results
    except Exception as e:
        results["errors"].append(f"Scrape error: {str(e)}")
        return results

    # Step 2: Generate proposals
    logger.info(f"📝 Generating proposals (workers={workers})")
    proposal_cmd = [
        sys.executable, "execution/upwork_proposal_generator.py",
        "--input", ".tmp/upwork_jobs_batch.json",
        "--workers", str(workers),
        "--output", ".tmp/upwork_jobs_with_proposals.json"
    ]
    if keywords:
        proposal_cmd.extend(["--filter-keywords", keywords])

    try:
        proposal_result = subprocess.run(
            proposal_cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min for proposal generation
            cwd=str(Path(__file__).parent.parent)
        )
        results["steps"].append({
            "step": "proposals",
            "returncode": proposal_result.returncode,
            "stdout": proposal_result.stdout[-2000:] if proposal_result.stdout else "",
            "stderr": proposal_result.stderr[-1000:] if proposal_result.stderr else ""
        })
        if proposal_result.returncode != 0:
            results["errors"].append(f"Proposal generation failed: {proposal_result.stderr}")
    except subprocess.TimeoutExpired:
        results["errors"].append("Proposal generation timed out after 30 minutes")
    except Exception as e:
        results["errors"].append(f"Proposal error: {str(e)}")

    # Try to load output
    output_path = Path(__file__).parent.parent / ".tmp/upwork_jobs_with_proposals.json"
    if output_path.exists():
        try:
            with open(output_path) as f:
                output_data = json.load(f)
            results["jobs_processed"] = len(output_data) if isinstance(output_data, list) else output_data.get("count", 0)
        except Exception:
            pass

    # Extract Google Sheet URL from proposal stdout
    import re
    proposal_stdout = results["steps"][-1]["stdout"] if results["steps"] else ""
    sheet_match = re.search(r'https://docs\.google\.com/spreadsheets/d/[a-zA-Z0-9_-]+', proposal_stdout)
    if sheet_match:
        results["sheet_url"] = sheet_match.group(0)

    results["status"] = "success" if not results["errors"] else "partial" if results.get("jobs_processed") else "failed"

    # Clean response - remove verbose stdout/stderr from steps
    results["steps"] = [{"step": s["step"], "status": "ok" if s["returncode"] == 0 else "failed"} for s in results["steps"]]

    return results


SCRIPT_HANDLERS["upwork_scrape_apply"] = run_upwork_scrape_apply


def run_script(script_name: str, input_data: dict) -> dict:
    """Run a script by name with input data."""
    if script_name in SCRIPT_HANDLERS:
        return SCRIPT_HANDLERS[script_name](input_data)

    # Generic script runner for other scripts
    script_path = Path(__file__).parent / f"{script_name}.py"
    if not script_path.exists():
        return {"error": f"Script not found: {script_name}.py"}

    # Write input to temp file
    input_file = Path(__file__).parent.parent / ".tmp" / f"{script_name}_input.json"
    input_file.parent.mkdir(exist_ok=True)
    with open(input_file, "w") as f:
        json.dump(input_data, f)

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--input", str(input_file)],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(Path(__file__).parent.parent)
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "stdout": result.stdout[-3000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else ""
        }
    except subprocess.TimeoutExpired:
        return {"error": "Script timed out after 10 minutes"}
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def load_webhook_config() -> dict:
    """Load webhook configuration."""
    config_path = Path("execution/webhooks.json")
    if not config_path.exists():
        return {"webhooks": {}}
    return json.loads(config_path.read_text())


def load_directive(directive_name: str) -> str:
    """Load a directive file."""
    directive_path = Path(f"directives/{directive_name}.md")
    if not directive_path.exists():
        raise FileNotFoundError(f"Directive not found: {directive_name}")
    return directive_path.read_text()


def run_directive(
    slug: str,
    directive_content: str,
    input_data: dict,
    allowed_tools: list,
    max_turns: int = 15
) -> dict:
    """Execute a directive with scoped tools."""
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Build prompt
    prompt = f"""You are executing a specific directive. Follow it precisely.

## DIRECTIVE
{directive_content}

## INPUT DATA
{json.dumps(input_data, indent=2) if input_data else "No input data provided."}

## INSTRUCTIONS
1. Read and understand the directive above
2. Use the available tools to accomplish the task
3. Report your results clearly

Execute the directive now."""

    # Filter tools
    tools = [ALL_TOOLS[t] for t in allowed_tools if t in ALL_TOOLS]

    messages = [{"role": "user", "content": prompt}]
    conversation_log = []
    thinking_log = []
    total_input_tokens = 0
    total_output_tokens = 0
    turn_count = 0

    logger.info(f"🎯 Executing directive: {slug}")

    response = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=16000,
        tools=tools,
        messages=messages,
        thinking={"type": "enabled", "budget_tokens": 32000}
    )

    total_input_tokens += response.usage.input_tokens
    total_output_tokens += response.usage.output_tokens

    while response.stop_reason == "tool_use" and turn_count < max_turns:
        turn_count += 1

        # Process thinking
        for block in response.content:
            if block.type == "thinking":
                thinking_log.append({"turn": turn_count, "thinking": block.thinking})
                logger.info(f"💭 Turn {turn_count} thinking: {block.thinking[:100]}...")

        # Find tool call
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if not tool_use:
            break

        # Security check
        if tool_use.name not in allowed_tools:
            tool_result = json.dumps({"error": f"Tool '{tool_use.name}' not permitted"})
            is_error = True
        else:
            logger.info(f"🔧 Turn {turn_count} - {tool_use.name}: {tool_use.input}")
            conversation_log.append({"turn": turn_count, "tool": tool_use.name, "input": tool_use.input})

            # Execute tool
            is_error = False
            try:
                impl = TOOL_IMPLEMENTATIONS.get(tool_use.name)
                if impl:
                    result = impl(**tool_use.input)
                    tool_result = json.dumps(result)
                else:
                    tool_result = json.dumps({"error": f"No implementation for {tool_use.name}"})
                    is_error = True
            except Exception as e:
                logger.error(f"Tool error: {e}")
                tool_result = json.dumps({"error": str(e)})
                is_error = True

            conversation_log[-1]["result"] = tool_result
            logger.info(f"{'❌' if is_error else '✅'} Result: {tool_result[:200]}")

        # Continue conversation
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tool_use.id, "content": tool_result}
        ]})

        response = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=16000,
            tools=tools,
            messages=messages,
            thinking={"type": "enabled", "budget_tokens": 32000}
        )

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

    # Extract final response
    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text += block.text
        if block.type == "thinking":
            thinking_log.append({"turn": "final", "thinking": block.thinking})

    usage = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "turns": turn_count
    }

    logger.info(f"✨ Complete - {usage['turns']} turns, {usage['input_tokens']}→{usage['output_tokens']} tokens")

    return {
        "response": final_text,
        "thinking": thinking_log,
        "conversation": conversation_log,
        "usage": usage
    }


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Server info."""
    return {
        "service": "Claude Orchestrator (Local)",
        "status": "running",
        "endpoints": {
            "webhook": "POST /webhook/{slug}",
            "list": "GET /webhooks"
        }
    }


@app.get("/webhooks")
async def list_webhooks():
    """List available webhooks."""
    config = load_webhook_config()
    webhooks = config.get("webhooks", {})

    return {
        "webhooks": {
            slug: {
                "directive": cfg.get("directive"),
                "script": cfg.get("script"),
                "description": cfg.get("description", ""),
                "tools": cfg.get("tools", [])
            }
            for slug, cfg in webhooks.items()
        }
    }


@app.post("/webhook/{slug}")
async def execute_webhook(slug: str, payload: Optional[dict] = None):
    """Execute a directive or script by slug."""
    payload = payload or {}
    input_data = payload.get("data", payload)
    max_turns = payload.get("max_turns", 15)

    # Load config
    config = load_webhook_config()
    webhooks = config.get("webhooks", {})

    if slug not in webhooks:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown webhook slug: {slug}"
        )

    webhook_config = webhooks[slug]
    directive_name = webhook_config.get("directive")
    script_name = webhook_config.get("script")

    # Handle script-type webhooks
    if script_name:
        logger.info(f"🔧 Running script: {script_name}")
        try:
            result = run_script(script_name, input_data)
            return {
                "status": result.get("status", "completed"),
                "slug": slug,
                "mode": "local",
                "type": "script",
                "script": script_name,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Script error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Handle directive-type webhooks
    if not directive_name:
        raise HTTPException(
            status_code=400,
            detail="Webhook must have either 'directive' or 'script' defined"
        )

    allowed_tools = webhook_config.get("tools", ["send_email"])

    try:
        directive_content = load_directive(directive_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        result = run_directive(
            slug=slug,
            directive_content=directive_content,
            input_data=input_data,
            allowed_tools=allowed_tools,
            max_turns=max_turns
        )

        return {
            "status": "success",
            "slug": slug,
            "mode": "local",
            "type": "directive",
            "directive": directive_name,
            "response": result["response"],
            "thinking": result["thinking"],
            "conversation": result["conversation"],
            "usage": result["usage"],
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
