import os
import json
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from centralized /etc/uisp path
ENV_PATH = "/etc/uisp/uisp.env"
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
else:
    # Fallback to old path for backward compatibility
    legacy_path = "/etc/uisp_suspend_unsuspend/uisp_suspend_unsuspend.env"
    if os.path.exists(legacy_path):
        load_dotenv(legacy_path)


@dataclass
class Router:
    site: str
    name: str
    api_url: str
    username: str
    password: str
    dhcp_ranges: list[str]


@dataclass
class AppConfig:
    env: str
    bind_ip: str
    port: int
    log_level: str
    telegram_token: str
    telegram_chat_id: str
    uisp_base_url: str
    uisp_app_key: str
    whatsapp_phone_id: str
    whatsapp_token: str
    tls_verify: bool
    routers: list[Router]


def load_config() -> AppConfig:
    """Load configuration from .env and NAS config."""
    env = os.getenv("ENV", "production")
    bind_ip = os.getenv("BIND_IP", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "info")

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    uisp_base_url = os.getenv("UISP_BASE_URL", "https://uisp-ros1.afrieta.com/")
    uisp_app_key = os.getenv("UISP_APP_KEY", "")
    whatsapp_phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    whatsapp_token = os.getenv("WHATSAPP_TOKEN", "")
    tls_verify = os.getenv("TLS_VERIFY", "true").lower() == "true"

    nas_config_path = os.getenv("NAS_CONFIG_PATH", "/etc/uisp/nas_config.json")

    routers = []
    if os.path.exists(nas_config_path):
        with open(nas_config_path, "r") as f:
            data = json.load(f)
        
        # Handle the site-based structure (e.g., {"Milpark": {...}, "Roshcor": {...}})
        for site_name, site_config in data.items():
            if isinstance(site_config, dict) and "api_url" in site_config:
                # Convert dash-range to CIDR if needed
                dhcp_range = site_config.get("dhcp_range", "")
                dhcp_ranges = []
                
                if dhcp_range and "-" in dhcp_range:
                    # Convert "100.64.16.21-100.64.17.254" to CIDR approximation
                    dhcp_ranges = [convert_range_to_cidr(dhcp_range)]
                elif dhcp_range:
                    dhcp_ranges = [dhcp_range]
                
                routers.append(
                    Router(
                        site=site_name,
                        name=site_config.get("router_ip", site_name),
                        api_url=site_config.get("api_url", ""),
                        username=site_config.get("username", ""),
                        password=site_config.get("password", ""),
                        dhcp_ranges=dhcp_ranges,
                    )
                )

    return AppConfig(
        env=env,
        bind_ip=bind_ip,
        port=port,
        log_level=log_level,
        telegram_token=telegram_token,
        telegram_chat_id=telegram_chat_id,
        uisp_base_url=uisp_base_url,
        uisp_app_key=uisp_app_key,
        whatsapp_phone_id=whatsapp_phone_id,
        whatsapp_token=whatsapp_token,
        tls_verify=tls_verify,
        routers=routers,
    )


def convert_range_to_cidr(ip_range: str) -> str:
    """
    Convert IP range like '100.64.16.21-100.64.17.254' to CIDR notation.
    This is a simplified conversion - for precise control, update your config to use CIDR.
    """
    import ipaddress
    
    try:
        start_ip, end_ip = ip_range.split("-")
        start = ipaddress.IPv4Address(start_ip.strip())
        end = ipaddress.IPv4Address(end_ip.strip())
        
        # Find the network that encompasses both IPs
        # This is a simplified approach - calculates the smallest network containing the range
        for prefix_len in range(32, 0, -1):
            try:
                # Try to create a network from start IP with this prefix
                network = ipaddress.IPv4Network(f"{start}/{prefix_len}", strict=False)
                if start in network and end in network:
                    return str(network)
            except:
                continue
        
        # Fallback: use /24 network of start IP
        return str(ipaddress.IPv4Network(f"{start}/24", strict=False))
    except Exception as e:
        # If conversion fails, return a safe default
        return "0.0.0.0/0"


def find_router_by_ip(cfg: AppConfig, ip: str) -> tuple[str, Router | None]:
    """Find router responsible for a given IP based on DHCP ranges."""
    import ipaddress

    for router in cfg.routers:
        for r in router.dhcp_ranges:
            if ipaddress.ip_address(ip) in ipaddress.ip_network(r):
                return router.site, router
    return "Unknown", None
