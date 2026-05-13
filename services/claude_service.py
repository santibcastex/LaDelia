from anthropic import Anthropic
import base64
import json
import logging

logger = logging.getLogger(__name__)

class ClaudeService:
    def __init__(self):
        self.client = Anthropic()
        self.model = "claude-3-5-sonnet-20241022"
    
    async def extract_invoice_data(self, image_bytes: bytes) -> dict:
        try:
            base64_image = base64.standard_b64encode(image_bytes).decode("utf-8")
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64_image,
                                },
                            },
                            {
                                "type": "text",
                                "text": """Sos un experto en facturas agrícolas de Argentina. Extrae estos datos:

- numero_factura: Número/referencia de factura
- fecha: DD/MM/YYYY
- contratista: Nombre de quien emite
- importe_total: Monto en pesos (solo número)
- descripcion: Qué trabajo se hizo
- lote: Campo o lote donde se hizo el trabajo (si aparece)
- tipo_trabajo: Categoría (aplicación herbicida, cosecha, etc)

Responde SOLO en JSON, sin markdown.
Si algo no está claro, pon null.

Ejemplo:
{"numero_factura": "001", "fecha": "15/03/2024", ...}"""
                            }
                        ],
                    }
                ],
            )
            
            response_text = message.content[0].text.strip()
            
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            factura_data = json.loads(response_text)
            logger.info(f"Factura extraída: {factura_data.get('numero_factura')}")
            return factura_data
        
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON: {str(e)}")
            return {
                "numero_factura": "ERROR",
                "error": "No se pudo procesar la factura."
            }
        except Exception as e:
            logger.error(f"Error en extract_invoice_data: {str(e)}")
            raise
