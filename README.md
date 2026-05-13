# Agro Neros - Sistema de Facturas WhatsApp

Backend FastAPI para procesar facturas de contratistas vía WhatsApp usando Claude Vision y Firestore.

## Setup Local

```bash
# Clonar y entrar al directorio
cd backend

# Crear venv
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Crear archivo .env con las credenciales (ver instrucciones en el issue)
cp .env.example .env
# Editar .env con tus valores reales

# Correr localmente
uvicorn main:app --reload
```

## Deploy en Vercel

1. **Conectar GitHub a Vercel:**
   - Ir a https://vercel.com
   - Click "New Project"
   - Seleccionar repo
   - Click "Deploy"

2. **Agregar variables de entorno en Vercel:**
   - Project Settings → Environment Variables
   - Agregar:
     - `TWILIO_ACCOUNT_SID`
     - `TWILIO_AUTH_TOKEN`
     - `TWILIO_PHONE`
     - `ANTHROPIC_API_KEY`
     - `GOOGLE_APPLICATION_CREDENTIALS` (pegar contenido del JSON)

3. **Obtener URL del deploy:**
   - Vercel te da algo como: `https://proyecto.vercel.app`
   - Tu webhook será: `https://proyecto.vercel.app/webhook`

4. **Configurar webhook en Twilio:**
   - Dashboard Twilio → Messaging → Sandbox Settings
   - "When a message comes in" → `https://proyecto.vercel.app/webhook`
   - Method: POST
   - Click "Save"

## API Endpoints

- `GET /` - Health check
- `POST /webhook` - Recibe mensajes de WhatsApp
- `POST /admin/approve-invoice/{factura_id}` - Aprobar factura
- `POST /admin/reject-invoice/{factura_id}` - Rechazar factura

## Flujo

1. Contratista envía foto de factura por WhatsApp
2. Twilio recibe y envía a `/webhook`
3. Claude Vision extrae datos
4. Se guarda en Firestore con estado "pendiente_validacion"
5. Admin aprueba/rechaza desde panel React
6. Contratista recibe notificación de resultado

## Notas

- El archivo `facturas-la-delia-b38a31936715.json` contiene credenciales de Firebase
- No commitear `.env` ni archivos con credenciales
- Las variables de entorno en Vercel se cargan automáticamente
