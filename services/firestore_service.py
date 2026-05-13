import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

class FirestoreService:
    def __init__(self):
        if not firebase_admin._apps:
            import json
            
            # Intentar leer desde archivo local primero
            cred_path = "facturas-la-delia-b38a31936715.json"
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
            else:
                # Si no existe archivo, leer desde variable de entorno
                cred_json_str = os.getenv("FIREBASE_CREDENTIALS_JSON")
                if not cred_json_str:
                    cred_json_str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                
                if cred_json_str:
                    cred_dict = json.loads(cred_json_str)
                    cred = credentials.Certificate(cred_dict)
                else:
                    raise ValueError("Firebase credentials not found")
            
            firebase_admin.initialize_app(cred)
        
        self.db = firestore.client()
    
    async def save_invoice(self, factura_data: dict, phone_number: str, image_base64: str) -> str:
        try:
            factura_id = f"{factura_data.get('numero_factura')}_{datetime.now().timestamp()}"
            
            doc_data = {
                "datos": factura_data,
                "estado": "pendiente_validacion",
                "contratista_whatsapp": phone_number,
                "fecha_ingreso": datetime.now(),
                "notas": [],
                "image_base64": image_base64,
                "fecha_actualizacion": datetime.now()
            }
            
            self.db.collection("facturas").document(factura_id).set(doc_data)
            
            logger.info(f"Factura guardada: {factura_id}")
            return factura_id
        
        except Exception as e:
            logger.error(f"Error guardando en Firestore: {str(e)}")
            raise
    
    async def get_invoice(self, factura_id: str) -> dict:
        try:
            doc = self.db.collection("facturas").document(factura_id).get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                return None
        
        except Exception as e:
            logger.error(f"Error obteniendo factura: {str(e)}")
            return None
    
    async def update_invoice_status(self, factura_id: str, status: str, notas: str = ""):
        try:
            self.db.collection("facturas").document(factura_id).update({
                "estado": status,
                "fecha_actualizacion": datetime.now(),
                "notas": firestore.ArrayUnion([f"{status}: {notas}"])
            })
            
            logger.info(f"Factura {factura_id} actualizada a {status}")
        
        except Exception as e:
            logger.error(f"Error actualizando: {str(e)}")
            raise
    
    async def get_all_invoices(self, status_filter: str = None) -> list:
        try:
            if status_filter:
                query = self.db.collection("facturas").where("estado", "==", status_filter)
            else:
                query = self.db.collection("facturas")
            
            docs = query.stream()
            
            facturas = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                facturas.append(data)
            
            return facturas
        
        except Exception as e:
            logger.error(f"Error obteniendo facturas: {str(e)}")
            return []
