from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import logging
import base64

from services.twilio_service import TwilioService
from services.claude_service import ClaudeService
from services.firestore_service import FirestoreService

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="La Delia - Facturas API")

# CORS permisivo para Twilio
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"📡 {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"✅ Response: {response.status_code}")
    return response

twilio_service = TwilioService()
claude_service = ClaudeService()
firestore_service = FirestoreService()

user_contexts = {}

@app.get("/")
def root():
    return {"status": "ok", "service": "La Delia - Facturas API"}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": "now"}

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    """Webhook para recibir mensajes de Twilio"""
    logger.info("🔔 ========== WEBHOOK POST RECIBIDO ==========")
    
    try:
        form_data = await request.form()
        logger.info(f"📋 Form data keys: {list(form_data.keys())}")
        
        phone_number = form_data.get("From", "unknown")
        media_url = form_data.get("MediaUrl0")
        message_body = form_data.get("Body", "")
        
        logger.info(f"📱 De: {phone_number}")
        logger.info(f"💬 Mensaje: {message_body}")
        logger.info(f"🖼️ Media: {bool(media_url)}")
        
        phone_clean = phone_number.replace("whatsapp:", "") if phone_number else "unknown"
        
        # Respuesta simple de prueba
        test_response = "✅ Webhook recibido correctamente!"
        logger.info(f"📤 Enviando respuesta a {phone_clean}")
        
        try:
            await twilio_service.send_message(phone_clean, test_response)
            logger.info("✅ Respuesta enviada exitosamente")
        except Exception as send_error:
            logger.error(f"❌ Error enviando respuesta: {str(send_error)}", exc_info=True)
        
        logger.info("🔔 ========== WEBHOOK FINALIZADO ==========")
        return PlainTextResponse("")
        
    except Exception as e:
        logger.error(f"❌ Error en webhook: {str(e)}", exc_info=True)
        logger.info("🔔 ========== WEBHOOK FINALIZADO CON ERROR ==========")
        return PlainTextResponse("")

@app.post("/admin/approve-invoice/{factura_id}")
async def approve_invoice(factura_id: str, request: Request):
    try:
        data = await request.json()
        notas = data.get("notas", "")
        
        await firestore_service.update_invoice_status(
            factura_id=factura_id,
            status="aprobada",
            notas=notas
        )
        
        factura_doc = await firestore_service.get_invoice(factura_id)
        phone = factura_doc.get("contratista_whatsapp")
        
        msg = f"""✅ *Tu factura fue aprobada*

Número: {factura_doc.get('datos', {}).get('numero_factura')}
Importe: ${factura_doc.get('datos', {}).get('importe_total')}

Gracias por tu trabajo."""
        
        await twilio_service.send_message(phone, msg)
        
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"Error aprobando: {str(e)}")
        return {"status": "error", "detail": str(e)}

@app.post("/admin/reject-invoice/{factura_id}")
async def reject_invoice(factura_id: str, request: Request):
    try:
        data = await request.json()
        notas = data.get("notas", "Datos incorrectos. Por favor reenvía.")
        
        await firestore_service.update_invoice_status(
            factura_id=factura_id,
            status="rechazada",
            notas=notas
        )
        
        factura_doc = await firestore_service.get_invoice(factura_id)
        phone = factura_doc.get("contratista_whatsapp")
        
        msg = f"""❌ *Tu factura necesita correcciones*

Número: {factura_doc.get('datos', {}).get('numero_factura')}

💬 Motivo:
_{notas}_

Enviá una nueva foto con los datos correctos."""
        
        await twilio_service.send_message(phone, msg)
        
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"Error rechazando: {str(e)}")
        return {"status": "error", "detail": str(e)}
