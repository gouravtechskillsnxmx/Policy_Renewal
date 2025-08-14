# whatsapp.py
import os
from dotenv import load_dotenv
load_dotenv()

TW_SID = os.getenv("TWILIO_SID")
TW_TOKEN = os.getenv("TWILIO_TOKEN")
TW_FROM = os.getenv("TWILIO_WHATSAPP_FROM")  # e.g. 'whatsapp:+1415...'

def send_whatsapp(to_number: str, message: str) -> str | None:
    """
    Returns:
      - "SIMULATED-SEND" if no Twilio creds
      - Twilio SID string if success
      - None if failed (and prints error)
    """
    if not (TW_SID and TW_TOKEN and TW_FROM):
        print(f"[SIMULATION] Would send to {to_number}: {message}")
        return "SIMULATED-SEND"
    try:
        from twilio.rest import Client
        client = Client(TW_SID, TW_TOKEN)
        msg = client.messages.create(
            body=message, from_=TW_FROM, to=f"whatsapp:{to_number}"
        )
        return msg.sid
    except Exception as e:
        print("Twilio send failed:", e)
        return None
