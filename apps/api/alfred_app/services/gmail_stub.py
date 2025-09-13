from datetime import datetime, timedelta, timezone

def fetch_last_24h_emails(profile_id: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {"from":"recruiter@company.com","subject":"Interview next week",
         "snippet":"Can you do Tue 11am ET?","received_ts":(now-timedelta(hours=3)).isoformat(),
         "body_text":"Let me know your availability for next week."},
        {"from":"alerts@finnews.com","subject":"Market wrap",
         "snippet":"Stocks rallied...","received_ts":(now-timedelta(hours=6)).isoformat(),
         "body_text":"S&P +1.1%, Nasdaq +1.4%."},
    ]
# Wire Google Gmail API OAuth when ready (see Python quickstart docs). :contentReference[oaicite:9]{index=9}
