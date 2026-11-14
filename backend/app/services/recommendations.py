"""Illustrative actions for the demo dashboard, never site-specific instructions."""

RECOMMENDATIONS = {
    "LOW": "Continue routine monitoring and scheduled inspections under site procedures.",
    "MEDIUM": "Increase monitoring frequency and request inspection of the affected area.",
    "HIGH": "Restrict access as appropriate and request an urgent geotechnical inspection.",
    "CRITICAL": "Escalate to mine safety personnel and follow the site's emergency procedures.",
}


def recommendation(level: str) -> str:
    return RECOMMENDATIONS.get(level, "Follow approved mine-specific safety procedures.")
