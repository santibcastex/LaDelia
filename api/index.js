const express = require('express');
const bodyParser = require('body-parser');
const twilio = require('twilio');
const Anthropic = require('@anthropic-ai/sdk');
const admin = require('firebase-admin');
const axios = require('axios');
require('dotenv').config();

const app = express();

app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());

// Twilio
const accountSid = process.env.TWILIO_ACCOUNT_SID;
const authToken = process.env.TWILIO_AUTH_TOKEN;
const twilioPhone = process.env.TWILIO_PHONE;
const twilioClient = twilio(accountSid, authToken);

// Claude
const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// Firebase - soporte para credenciales como JSON string o path
function initFirebase() {
  if (admin.apps.length) return;

  const credentialsEnv = process.env.GOOGLE_APPLICATION_CREDENTIALS;
  if (!credentialsEnv) {
    console.warn('⚠️  GOOGLE_APPLICATION_CREDENTIALS no configurado');
    return;
  }

  let credential;
  try {
    // Si es JSON inline (Vercel lo guarda así)
    const parsed = JSON.parse(credentialsEnv);
    credential = admin.credential.cert(parsed);
  } catch {
    // Si es un path a archivo
    credential = admin.credential.cert(require(credentialsEnv));
  }

  admin.initializeApp({ credential });
}

initFirebase();

function getDb() {
  if (!admin.apps.length) return null;
  return admin.firestore();
}

// Descarga imagen de Twilio con autenticación básica
async function downloadImage(mediaUrl) {
  const response = await axios.get(mediaUrl, {
    auth: { username: accountSid, password: authToken },
    responseType: 'arraybuffer',
    timeout: 15000,
  });
  const contentType = response.headers['content-type'] || 'image/jpeg';
  const base64 = Buffer.from(response.data).toString('base64');
  return { base64, contentType };
}

// Extrae datos de factura con Claude Vision
async function extractInvoiceData(imageBase64, contentType) {
  const response = await anthropic.messages.create({
    model: 'claude-opus-4-7',
    max_tokens: 1024,
    messages: [
      {
        role: 'user',
        content: [
          {
            type: 'image',
            source: { type: 'base64', media_type: contentType, data: imageBase64 },
          },
          {
            type: 'text',
            text: `Analizá esta factura y extraé los datos en formato JSON con estos campos:
{
  "proveedor": "nombre del proveedor o emisor",
  "numero_factura": "número de factura",
  "fecha": "fecha en formato YYYY-MM-DD",
  "monto_total": número (sin símbolo, solo el número),
  "moneda": "ARS o USD",
  "concepto": "descripción breve del servicio o producto",
  "cuit_emisor": "CUIT del emisor si aparece"
}
Si algún campo no está visible, usá null. Respondé SOLO con el JSON, sin texto adicional.`,
          },
        ],
      },
    ],
  });

  const text = response.content[0].text.trim();
  try {
    return JSON.parse(text);
  } catch {
    // Intentar extraer JSON si Claude agregó algo extra
    const match = text.match(/\{[\s\S]*\}/);
    if (match) return JSON.parse(match[0]);
    throw new Error('Claude no devolvió JSON válido: ' + text);
  }
}

// Health check
app.get('/', (req, res) => {
  res.json({ status: 'ok', service: 'La Delia - Facturas API' });
});

// Webhook de Twilio
app.post('/webhook', async (req, res) => {
  const twiml = new twilio.twiml.MessagingResponse();

  try {
    console.log('🔔 WEBHOOK RECIBIDO');

    const from = req.body.From || '';
    const body = req.body.Body || '';
    const mediaUrl = req.body.MediaUrl0;
    const numMedia = parseInt(req.body.NumMedia || '0', 10);

    console.log(`📱 De: ${from}`);
    console.log(`💬 Mensaje: ${body}`);
    console.log(`🖼️  Media: ${numMedia > 0}`);

    const phoneClean = from.replace('whatsapp:', '');

    if (numMedia === 0 || !mediaUrl) {
      twiml.message(
        '👋 Hola! Enviá una foto de tu factura y la procesaremos automáticamente.'
      );
      res.type('text/xml');
      return res.send(twiml.toString());
    }

    // Acuse de recibo inmediato
    twiml.message('📥 Factura recibida! Estamos procesándola, un momento...');
    res.type('text/xml');
    res.send(twiml.toString());

    // Procesamiento async después de responder a Twilio
    setImmediate(async () => {
      try {
        const { base64, contentType } = await downloadImage(mediaUrl);
        console.log('🖼️  Imagen descargada, enviando a Claude...');

        const invoiceData = await extractInvoiceData(base64, contentType);
        console.log('📊 Datos extraídos:', invoiceData);

        const db = getDb();
        let facturaId = null;

        if (db) {
          const docRef = await db.collection('facturas').add({
            ...invoiceData,
            phone: phoneClean,
            mediaUrl,
            estado: 'pendiente_validacion',
            creadoEn: admin.firestore.FieldValue.serverTimestamp(),
          });
          facturaId = docRef.id;
          console.log(`💾 Guardado en Firestore: ${facturaId}`);
        }

        const resumen = [
          `✅ *Factura procesada!*`,
          invoiceData.proveedor ? `🏢 Proveedor: ${invoiceData.proveedor}` : null,
          invoiceData.numero_factura ? `🔢 Nº: ${invoiceData.numero_factura}` : null,
          invoiceData.fecha ? `📅 Fecha: ${invoiceData.fecha}` : null,
          invoiceData.monto_total != null
            ? `💰 Total: ${invoiceData.moneda || ''} ${invoiceData.monto_total}`
            : null,
          invoiceData.concepto ? `📝 ${invoiceData.concepto}` : null,
          `\nEstado: _Pendiente de validación_`,
        ]
          .filter(Boolean)
          .join('\n');

        await twilioClient.messages.create({
          from: `whatsapp:${twilioPhone}`,
          to: from,
          body: resumen,
        });

        console.log('📤 Resumen enviado al usuario');
      } catch (err) {
        console.error('❌ Error procesando factura:', err);
        await twilioClient.messages.create({
          from: `whatsapp:${twilioPhone}`,
          to: from,
          body: '❌ Hubo un error procesando tu factura. Intentá de nuevo o contactá al administrador.',
        });
      }
    });
  } catch (error) {
    console.error('❌ Error en webhook:', error);
    twiml.message('❌ Error interno. Intentá de nuevo.');
    res.type('text/xml');
    res.send(twiml.toString());
  }
});

// Aprobar factura
app.post('/admin/approve-invoice/:facturaId', async (req, res) => {
  const { facturaId } = req.params;
  const db = getDb();

  if (!db) return res.status(503).json({ error: 'Firestore no disponible' });

  try {
    const ref = db.collection('facturas').doc(facturaId);
    const doc = await ref.get();

    if (!doc.exists) return res.status(404).json({ error: 'Factura no encontrada' });

    await ref.update({
      estado: 'aprobada',
      aprobadaEn: admin.firestore.FieldValue.serverTimestamp(),
    });

    const data = doc.data();
    if (data.phone) {
      await twilioClient.messages.create({
        from: `whatsapp:${twilioPhone}`,
        to: `whatsapp:${data.phone}`,
        body: `✅ Tu factura ${data.numero_factura || facturaId} fue *aprobada*. Será procesada en el próximo ciclo de pagos.`,
      });
    }

    res.json({ ok: true, facturaId, estado: 'aprobada' });
  } catch (err) {
    console.error('Error aprobando factura:', err);
    res.status(500).json({ error: err.message });
  }
});

// Rechazar factura
app.post('/admin/reject-invoice/:facturaId', async (req, res) => {
  const { facturaId } = req.params;
  const { motivo } = req.body;
  const db = getDb();

  if (!db) return res.status(503).json({ error: 'Firestore no disponible' });

  try {
    const ref = db.collection('facturas').doc(facturaId);
    const doc = await ref.get();

    if (!doc.exists) return res.status(404).json({ error: 'Factura no encontrada' });

    await ref.update({
      estado: 'rechazada',
      motivoRechazo: motivo || null,
      rechazadaEn: admin.firestore.FieldValue.serverTimestamp(),
    });

    const data = doc.data();
    if (data.phone) {
      const msg = motivo
        ? `❌ Tu factura ${data.numero_factura || facturaId} fue *rechazada*. Motivo: ${motivo}`
        : `❌ Tu factura ${data.numero_factura || facturaId} fue *rechazada*. Contactá al administrador para más información.`;

      await twilioClient.messages.create({
        from: `whatsapp:${twilioPhone}`,
        to: `whatsapp:${data.phone}`,
        body: msg,
      });
    }

    res.json({ ok: true, facturaId, estado: 'rechazada' });
  } catch (err) {
    console.error('Error rechazando factura:', err);
    res.status(500).json({ error: err.message });
  }
});

// Listar facturas (útil para el panel admin)
app.get('/admin/invoices', async (req, res) => {
  const db = getDb();
  if (!db) return res.status(503).json({ error: 'Firestore no disponible' });

  try {
    const { estado } = req.query;
    let query = db.collection('facturas').orderBy('creadoEn', 'desc').limit(50);
    if (estado) query = query.where('estado', '==', estado);

    const snapshot = await query.get();
    const facturas = snapshot.docs.map((d) => ({ id: d.id, ...d.data() }));
    res.json({ facturas });
  } catch (err) {
    console.error('Error listando facturas:', err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = app;
