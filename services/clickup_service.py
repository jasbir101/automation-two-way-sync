import os, requests
from dotenv import load_dotenv
load_dotenv()

CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
CLICKUP_LIST_ID = os.getenv("CLICKUP_LIST_ID")

class ClickUpService:
    def __init__(self):
        if not CLICKUP_API_TOKEN or not CLICKUP_LIST_ID:
            raise RuntimeError("ClickUp API token and list id must be set in .env")
        self.base = "https://api.clickup.com/api/v2"
        self.headers = {"Authorization": CLICKUP_API_TOKEN, "Content-Type": "application/json"}

    def create_task(self, list_id, name, status, description, custom_fields=None):
        payload = {"name": name, "status": status, "description": description}
        if custom_fields:
            payload["custom_fields"] = custom_fields
        resp = requests.post(f"{self.base}/list/{list_id}/task", headers=self.headers, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def update_task(self, task_id, fields):
        resp = requests.put(f"{self.base}/task/{task_id}", headers=self.headers, json=fields, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def get_tasks_in_list(self, list_id):
        resp = requests.get(f"{self.base}/list/{list_id}/task", headers=self.headers, timeout=20)
        resp.raise_for_status()
        return resp.json()
