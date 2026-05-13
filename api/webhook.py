import json
import os
import sys
import base64
from datetime import datetime

def handler(request):
    """Handler para Vercel Serverless Functions"""
    
    print(f"🔔 WEBHOOK RECIBIDO: {request.method}")
    
    if request.method == 'GET':
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'ok', 'service': 'La Delia - Facturas API'})
        }
    
    if request.method == 'POST':
        try:
            # Importar Twilio
            from twilio.rest import Client
            
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
            
            # Inicializar cliente Twilio
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            twilio_phone = os.getenv('TWILIO_PHONE')
            
            print(f"🔑 Twilio SID: {account_sid[:10] if account_sid else 'MISSING'}...")
            
            if not account_sid or not auth_token:
                print("❌ Credenciales Twilio no configuradas")
                return {'statusCode': 200, 'body': ''}
            
            client = Client(account_sid, auth_token)
            
            # Enviar respuesta por WhatsApp
            response_msg = "✅ Factura recibida! Estamos procesándola..."
            
            message = client.messages.create(
                from_=f'whatsapp:{twilio_phone}',
                to=f'whatsapp:{phone_clean}',
                body=response_msg
            )
            
            print(f"✅ Mensaje enviado: {message.sid}")
            
            return {
                'statusCode': 200,
                'body': ''
            }
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                'statusCode': 200,
                'body': ''
            }
    
    return {
        'statusCode': 405,
        'body': 'Method not allowed'
    }

