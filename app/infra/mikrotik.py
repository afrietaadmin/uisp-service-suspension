import requests
import logging

class MikroTikClient:
    """Simple REST API client for MikroTik routers."""
    
    def __init__(self, api_url: str, username: str, password: str, verify: bool = True):
        self.api_url = api_url.rstrip("/")
        self.auth = (username, password)
        self.verify = verify
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.verify = verify
        logging.debug(f"Initialized MikroTikClient for {self.api_url}")

    def _req(self, method: str, path: str, **kwargs):
        url = f"{self.api_url}/{path.lstrip('/')}"
        logging.debug(f"Requesting MikroTik {method} {url}")
        try:
            response = self.session.request(method, url, timeout=15, **kwargs)
            response.raise_for_status()
            return response.json() if response.text else {}
        except Exception as e:
            logging.error(f"MikroTik API error ({url}): {e}")
            raise RuntimeError(f"Router operation failed: {e}")

    def list_leases(self):
        """List all DHCP leases."""
        return self._req("GET", "ip/dhcp-server/lease")

    def toggle_block_access(self, lease_id: str, block: bool):
        """Block or unblock access to a DHCP lease."""
        data = {"block-access": "yes" if block else "no"}
        return self._req("PATCH", f"ip/dhcp-server/lease/{lease_id}", json=data)
