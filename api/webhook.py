import json
import os
import sys
import base64
from datetime import datetime

# Agregar path para importar modules
sys.path.insert(0, '/var/task')

def handler(request):
    """Handler para Vercel Serverless Functions"""
    
    print(f"🔔 WEBHOOK RECIBIDO: {request.method} {request.path}")
    
    if request.method == 'GET':
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'ok', 'service': 'La Delia - Facturas API'})
        }
    
    if request.method == 'POST':
        try:
            # Leer form data de Twilio
            body = request.get('body', {})
            if isinstance(body, str):
                # Si es string, parsearlo
                import urllib.parse
                body = dict(urllib.parse.parse_qsl(body))
            
            phone_number = body.get('From', 'unknown')
            media_url = body.get('MediaUrl0')
            message_body = body.get('Body', '')
            
            print(f"📱 De: {phone_number}")
            print(f"💬 Mensaje: {message_body}")
            print(f"🖼️ Media: {bool(media_url)}")
            
            phone_clean = phone_number.replace('whatsapp:', '') if phone_number else 'unknown'
            
            # Respuesta simple de prueba
            response_msg = "✅ Webhook recibido correctamente!"
            
            print(f"✅ Respuesta enviada a {phone_clean}")
            
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
