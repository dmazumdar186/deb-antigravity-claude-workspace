import os
import json
import sys
import time
import re
import logging
import requests
from typing import Dict, Any, List
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to load dotenv if available, otherwise rely on environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_KEY = os.getenv("PANDADOC_API_KEY")
API_URL = "https://api.pandadoc.com/public/v1/documents"
TEMPLATE_UUID = os.getenv("PANDADOC_TEMPLATE_UUID", "G8GhAvKGa9D8dmpwTnEWyV")
TIMEOUT = int(os.getenv("PANDADOC_TIMEOUT", "30"))
RECIPIENT_ROLE = os.getenv("PANDADOC_RECIPIENT_ROLE", "Client")


@dataclass
class ProposalConfig:
    """Configuration for creating a PandaDoc proposal document."""
    client_first_name: str
    client_last_name: str
    client_email: str
    client_company: str
    project_title: str
    tokens: List[Dict[str, str]] = field(default_factory=list)

    def __post_init__(self):
        if not self.client_email or '@' not in self.client_email:
            raise ValueError("Valid client email is required")
        if not self.project_title:
            raise ValueError("Project title is required")


def validate_input(data: Dict[str, Any]) -> ProposalConfig:
    """
    Validates input JSON and maps fields to PandaDoc template tokens.

    Expected input structure:
    {
        "client": {"firstName": str, "lastName": str, "email": str, "company": str},
        "project": {
            "title": str,
            "monthOneInvestment": str,
            "monthTwoInvestment": str,
            "monthThreeInvestment": str,
            "problems": {"problem01": str, ..., "problem04": str},
            "benefits": {"benefit01": str, ..., "benefit04": str}
        },
        "generated": {"slideFooter": str, "contractFooterSlug": str, "createdDate": str}
    }
    """
    client = data.get("client", {})
    project = data.get("project", {})
    generated = data.get("generated", {})
    problems = project.get("problems", {})
    benefits = project.get("benefits", {})

    # Validate email format
    email = client.get("email", "")
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        raise ValueError(f"Invalid client email format: {email}")

    # Generate slide footer if not provided
    client_company = client.get("company", "Client")
    slide_footer = generated.get("slideFooter") or f"{client_company} x {{COMPANY_NAME}}"

    # Build token mapping - only include tokens with actual values
    token_mapping = {
        "Client.Company": client.get("company"),
        "Personalization.Project.Title": project.get("title"),
        "MonthOneInvestment": str(project.get("monthOneInvestment", "")) if project.get("monthOneInvestment") else None,
        "MonthTwoInvestment": str(project.get("monthTwoInvestment", "")) if project.get("monthTwoInvestment") else None,
        "MonthThreeInvestment": str(project.get("monthThreeInvestment", "")) if project.get("monthThreeInvestment") else None,
        "Personalization.Project.Problem01": problems.get("problem01"),
        "Personalization.Project.Problem02": problems.get("problem02"),
        "Personalization.Project.Problem03": problems.get("problem03"),
        "Personalization.Project.Problem04": problems.get("problem04"),
        "Personalization.Project.Benefit.01": benefits.get("benefit01"),
        "Personalization.Project.Benefit.02": benefits.get("benefit02"),
        "Personalization.Project.Benefit.03": benefits.get("benefit03"),
        "Personalization.Project.Benefit.04": benefits.get("benefit04"),
        "Slide.Footer": slide_footer,
        "Contract.FooterSlug": generated.get("contractFooterSlug"),
        "Document.CreatedDate": generated.get("createdDate"),
    }

    # Only include tokens with non-empty values
    tokens = [
        {"name": name, "value": value}
        for name, value in token_mapping.items()
        if value and str(value).strip()
    ]

    return ProposalConfig(
        client_first_name=client.get("firstName", ""),
        client_last_name=client.get("lastName", ""),
        client_email=email,
        client_company=client_company,
        project_title=project.get("title", ""),
        tokens=tokens
    )


def wait_for_document_ready(doc_id: str, headers: Dict[str, str], max_wait: int = 60) -> str:
    """
    Polls PandaDoc API until document is ready (status: document.uploaded).

    Returns the final status or raises if timeout exceeded.
    """
    start_time = time.time()
    poll_interval = 2

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_URL}/{doc_id}", headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            status = response.json().get("status")
            logger.debug(f"Document {doc_id} status: {status}")

            if status == "document.uploaded":
                return status
            elif status in ["document.error", "document.deleted"]:
                raise RuntimeError(f"Document entered error state: {status}")

            time.sleep(poll_interval)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Status check failed, retrying: {e}")
            time.sleep(poll_interval)

    raise TimeoutError(f"Document {doc_id} not ready after {max_wait}s")


def create_document(config: ProposalConfig) -> Dict[str, Any]:
    """Creates a PandaDoc document from template and waits for it to be ready."""
    if not API_KEY:
        raise ValueError("PANDADOC_API_KEY not found in environment variables")

    headers = {
        "Authorization": f"API-Key {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "name": config.project_title,
        "template_uuid": TEMPLATE_UUID,
        "recipients": [
            {
                "email": config.client_email,
                "firstName": config.client_first_name,
                "lastName": config.client_last_name,
                "role": RECIPIENT_ROLE
            }
        ],
        "tokens": config.tokens
    }

    logger.info(f"Creating document: {config.project_title} for {config.client_email}")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=TIMEOUT)
            response.raise_for_status()
            result = response.json()
            doc_id = result.get("id")

            logger.info(f"Document created with ID: {doc_id}, waiting for ready state...")

            # Wait for document to be ready before returning
            final_status = wait_for_document_ready(doc_id, headers)
            result["status"] = final_status

            return result

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Rate limited - use Retry-After header if available
                retry_after = int(e.response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
            elif attempt == max_retries - 1:
                raise RuntimeError(f"Failed to create document after {max_retries} attempts: {e}")
            else:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)

        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to create document after {max_retries} attempts: {e}")
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)


def main() -> None:
    """Main entry point - reads JSON input and creates PandaDoc document."""
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(json.dumps({"success": False, "error": {"message": f"Input file not found: {sys.argv[1]}"}}, indent=2))
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(json.dumps({"success": False, "error": {"message": f"Invalid JSON in file: {e}"}}, indent=2))
            sys.exit(1)
    else:
        try:
            input_str = sys.stdin.read()
            if not input_str.strip():
                print(json.dumps({"success": False, "error": {"message": "No input provided. Pass JSON via stdin or file path."}}, indent=2))
                sys.exit(1)
            data = json.loads(input_str)
        except json.JSONDecodeError as e:
            print(json.dumps({"success": False, "error": {"message": f"Failed to parse JSON input: {e}"}}, indent=2))
            sys.exit(1)

    try:
        config = validate_input(data)
        result = create_document(config)

        doc_id = result.get("id")
        response = {
            "success": True,
            "documentId": doc_id,
            "internalLink": f"https://app.pandadoc.com/a/#/documents/{doc_id}" if doc_id else None,
            "documentName": config.project_title,
            "recipientEmail": config.client_email,
            "status": result.get("status")
        }
        print(json.dumps(response, indent=2))

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        print(json.dumps({"success": False, "error": {"message": str(e), "type": "validation"}}, indent=2))
        sys.exit(1)
    except RuntimeError as e:
        logger.error(f"API error: {e}")
        print(json.dumps({"success": False, "error": {"message": str(e), "type": "api"}}, indent=2))
        sys.exit(1)
    except TimeoutError as e:
        logger.error(f"Timeout error: {e}")
        print(json.dumps({"success": False, "error": {"message": str(e), "type": "timeout"}}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
