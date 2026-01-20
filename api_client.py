import requests
import json
from datetime import datetime
from config import config
import streamlit as st

class APIClient:
    def __init__(self):
        self.base_url = config.API_BASE_URL
        self.timeout = config.API_TIMEOUT

    def send_production_data(self, data):
        """Send production data to API"""
        endpoint = f"{self.base_url}{config.API_ENDPOINT}"

        try:
            # Format data as required by your API
            payload = self._format_payload(data)

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            response.raise_for_status()

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "data": result,
                    "message": "Calculation completed successfully"
                }
            else:
                return {
                    "success": False,
                    "message": f"API returned status {response.status_code}"
                }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"API request failed: {str(e)}"
            }
        except json.JSONDecodeError:
            return {
                "success": False,
                "message": "Invalid response from API"
            }

    def _format_payload(self, data):
        """Format data according to API requirements"""
        # Adjust this based on your API's expected format
        print(data)
        payload = {
            "metadata": data.get("metadata", {}),
            "chaine": data.get("chaine", {}),
            "employes": data.get("employes", []),
            "game": data.get("game", {}),
            "operations": data.get("operations", []),
            "parametres_production": data.get("parametres_production", {})
        }
        return payload


# Create a singleton instance
api_client = APIClient()