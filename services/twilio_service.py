from twilio.rest import Client
import os
import httpx
import logging

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.phone = os.getenv("TWILIO_PHONE")
        
        self.client = Client(self.account_sid, self.auth_token)
    
    async def send_message(self, to_number: str, message: str) -> dict:
        try:
            msg = self.client.messages.create(
                from_=f"whatsapp:{self.phone}",
                to=f"whatsapp:{to_number}",
                body=message
            )
            
            logger.info(f"Mensaje enviado a {to_number}: {msg.sid}")
            return {"status": "ok", "sid": msg.sid}
        
        except Exception as e:
            logger.error(f"Error enviando mensaje: {str(e)}")
            raise
    
    async def download_media(self, media_url: str) -> bytes:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    media_url,
                    auth=(self.account_sid, self.auth_token)
                )
                response.raise_for_status()
                
                logger.info(f"Imagen descargada: {len(response.content)} bytes")
                return response.content
        
        except Exception as e:
            logger.error(f"Error descargando media: {str(e)}")
            raise
