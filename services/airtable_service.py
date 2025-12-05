import os, requests
from dotenv import load_dotenv
load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Leads")

class AirtableService:
    def __init__(self):
        if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
            raise RuntimeError("Airtable API key and base id must be set in .env")
        self.base = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
        self.headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json"
        }

    def list_leads(self):
        resp = requests.get(self.base, headers=self.headers, timeout=20)
        resp.raise_for_status()
        return resp.json().get("records", [])

    def get_lead(self, rec_id):
        resp = requests.get(f"{self.base}/{rec_id}", headers=self.headers, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def update_lead(self, rec_id, fields):
        resp = requests.patch(f"{self.base}/{rec_id}", headers=self.headers, json={"fields": fields}, timeout=20)
        resp.raise_for_status()
        return resp.json()
