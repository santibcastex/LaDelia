from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
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

app = FastAPI(title="Agro Neros - Facturas API")

twilio_service = TwilioService()
claude_service = ClaudeService()
firestore_service = FirestoreService()

user_contexts = {}

@app.get("/")
def root():
    return {"status": "ok", "service": "Agro Neros Facturas API"}

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    try:
        form_data = await request.form()
        phone_number = form_data.get("From")
        message_body = form_data.get("Body", "")
        media_url = form_data.get("MediaUrl0")
        
        phone_clean = phone_number.replace("whatsapp:", "")
        logger.info(f"Mensaje recibido de {phone_clean}")
        
        if phone_clean not in user_contexts:
            user_contexts[phone_clean] = {
                "history": [],
                "factura_id": None,
                "estado": "esperando_accion"
            }
        
        if media_url:
            logger.info(f"Procesando imagen para {phone_clean}")
            image_bytes = await twilio_service.download_media(media_url)
            factura_data = await claude_service.extract_invoice_data(image_bytes)
            
            factura_id = await firestore_service.save_invoice(
                factura_data=factura_data,
                phone_number=phone_clean,
                image_base64=base64.standard_b64encode(image_bytes).decode("utf-8")
            )
            
            user_contexts[phone_clean]["factura_id"] = factura_id
            user_contexts[phone_clean]["estado"] = "factura_registrada"
            
            response_text = f"""✅ *Factura registrada correctamente*

📋 *Detalles:*
• Número: {factura_data.get('numero_factura')}
• Importe: ${factura_data.get('importe_total')}
• Campo: {factura_data.get('lote')}
• Estado: _Pendiente validación_

Escribí *"estado"* para consultar en cualquier momento."""
            
            await twilio_service.send_message(phone_clean, response_text)
            
        elif message_body.lower().strip() == "estado":
            logger.info(f"Consulta de estado desde {phone_clean}")
            context = user_contexts[phone_clean]
            
            if context["factura_id"]:
                factura_doc = await firestore_service.get_invoice(context["factura_id"])
                
                if factura_doc:
                    estado = factura_doc.get("estado")
                    datos = factura_doc.get("datos", {})
                    notas = factura_doc.get("notas", [])
                    
                    respuesta = f"""📋 *Estado de tu factura*

Número: {datos.get('numero_factura')}
Estado: *{estado.upper()}*
Importe: ${datos.get('importe_total')}"""
                    
                    if notas:
                        ultima_nota = notas[-1]
                        respuesta += f"\n\n💬 Última nota:\n_{ultima_nota}_"
                    
                    if estado == "rechazada":
                        respuesta += "\n\n❌ Por favor, reenvía con los datos correctos."
                    elif estado == "aprobada":
                        respuesta += "\n\n✅ Tu factura fue aprobada."
                else:
                    respuesta = "❌ No encontré tu factura. Enviá la foto de nuevo."
            else:
                respuesta = "📸 No tengo registro de facturas tuyas. Enviá una foto para comenzar."
            
            await twilio_service.send_message(phone_clean, respuesta)
        else:
            respuesta = """👋 Hola! Soy el asistente de Agro Neros.

Para registrar una factura:
📸 Enviá la *foto de la factura*

Para consultar estado:
📋 Escribí *"estado"*"""
            
            await twilio_service.send_message(phone_clean, respuesta)
        
        return PlainTextResponse("")
    
    except Exception as e:
        logger.error(f"Error en webhook: {str(e)}", exc_info=True)
        return PlainTextResponse("Error", status_code=500)

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
