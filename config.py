# Optional central config that reads from .env
import os
from dotenv import load_dotenv
load_dotenv()

CLICKUP_LIST_ID = os.getenv("CLICKUP_LIST_ID")
CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
CLICKUP_CUSTOM_FIELD_AIRTABLE_ID = os.getenv("CLICKUP_CUSTOM_FIELD_AIRTABLE_ID") or ""
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Leads")
