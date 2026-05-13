import json
import os
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

def handler(request):
    """Handler para Vercel Serverless Functions"""
    
    print(f"🔔 WEBHOOK RECIBIDO: {request.method}")
    
    if request.method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'ok', 'service': 'La Delia - Facturas API'})
        }
    
    if request.method == 'POST':
        try:
            # Leer form data de Twilio
            body = request.get('body', {})
            if isinstance(body, str):
                import urllib.parse
                body = dict(urllib.parse.parse_qsl(body))
            
            phone_number = body.get('From', 'unknown')
            media_url = body.get('MediaUrl0')
            message_body = body.get('Body', '')
            
            print(f"📱 De: {phone_number}")
            print(f"💬 Mensaje: {message_body}")
            print(f"🖼️ Media: {bool(media_url)}")
            
            phone_clean = phone_number.replace('whatsapp:', '') if phone_number else 'unknown'
            
            # Crear respuesta TwiML
            resp = MessagingResponse()
            resp.message("✅ Factura recibida! Estamos procesándola...")
            
            print(f"✅ Respuesta TwiML enviada")
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/xml'},
                'body': str(resp)
            }
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Devolver respuesta TwiML aunque haya error
            resp = MessagingResponse()
            resp.message("❌ Error procesando tu mensaje")
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/xml'},
                'body': str(resp)
            }
    
    return {
        'statusCode': 405,
        'body': 'Method not allowed'
    }


