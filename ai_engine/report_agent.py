def build_campaign_report(campaign):
    """Creates a practical campaign report from tracked metrics."""
    employees = int(campaign.get("employee_count") or 0)
    sent = int(campaign.get("emails_sent") or 0)
    failed = int(campaign.get("emails_failed") or 0)
    opens = int(campaign.get("opens") or 0)
    clicks = int(campaign.get("clicks") or 0)
    reports = int(campaign.get("reports") or 0)

    open_rate = round((opens / sent) * 100, 1) if sent else 0
    click_rate = round((clicks / sent) * 100, 1) if sent else 0
    report_rate = round((reports / sent) * 100, 1) if sent else 0
    delivery_rate = round((sent / employees) * 100, 1) if employees else 0

    if click_rate >= 35 or (clicks >= reports * 3 and clicks > 0):
        risk_level = "High"
        summary = "Employees interacted with the simulation more often than they reported it."
    elif click_rate >= 15:
        risk_level = "Medium"
        summary = "The campaign shows measurable click risk and needs targeted follow-up training."
    elif reports > clicks and reports > 0:
        risk_level = "Low"
        summary = "Reporting behavior is stronger than risky click behavior."
    else:
        risk_level = "Watch"
        summary = "The current result set is small or incomplete, so monitor the next campaign closely."

    recommendations = []
    if failed:
        recommendations.append("Fix failed email delivery before judging employee behavior.")
    if click_rate >= 15:
        recommendations.append("Run short training on link checking, urgency cues, and sender verification.")
    if report_rate < 10 and sent:
        recommendations.append("Make the reporting process easier and remind employees where the report button is.")
    if open_rate < 25 and sent:
        recommendations.append("Review email deliverability and whether images are blocked by the mail client.")
    if not recommendations:
        recommendations.append("Keep this scenario in the rotation and compare results with the next campaign.")

    return {
        "risk_level": risk_level,
        "summary": summary,
        "delivery_rate": delivery_rate,
        "open_rate": open_rate,
        "click_rate": click_rate,
        "report_rate": report_rate,
        "recommendations": recommendations,
    }
