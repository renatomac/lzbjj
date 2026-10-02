import logging
import requests
from django.conf import settings
from crm.models import Member
logger = logging.getLogger(__name__)
MAPBOX_GEOCODING_URL = "https://api.mapbox.com/search/geocode/v6/forward"
def member_address(member):
    return ", ".join(str(v).strip() for v in (member.address, member.city, member.state, member.zip_code, "USA") if v)
def geocode_member(member, *, timeout=10):
    token = getattr(settings, "MAPBOX_ACCESS_TOKEN", "")
    if not token:
        logger.warning("MAPBOX_ACCESS_TOKEN is not configured; skipping geocoding."); return False
    try:
        response = requests.get(MAPBOX_GEOCODING_URL, params={"q": member_address(member), "access_token": token, "limit": 1, "country": "US", "autocomplete": "false"}, timeout=timeout)
        response.raise_for_status(); features = response.json().get("features", [])
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Mapbox geocoding failed for member %s: %s", member.pk, exc); return False
    if not features: return False
    coordinates = features[0].get("geometry", {}).get("coordinates", [])
    if len(coordinates) < 2: return False
    longitude, latitude = coordinates[:2]
    Member.objects.filter(pk=member.pk).update(latitude=latitude, longitude=longitude)
    member.latitude, member.longitude = latitude, longitude
    return True
