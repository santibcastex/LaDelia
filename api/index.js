const express = require('express');
const bodyParser = require('body-parser');
const twilio = require('twilio');
const Anthropic = require('@anthropic-ai/sdk');
const admin = require('firebase-admin');
const axios = require('axios');

const app = express();

app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());

// ── Lazy singletons ─────────────────────────────────────────────────────────

let _twilioClient = null;
function getTwilioClient() {
  if (!_twilioClient) {
    _twilioClient = twilio(
      process.env.TWILIO_ACCOUNT_SID,
      process.env.TWILIO_AUTH_TOKEN
    );
  }
  return _twilioClient;
}

let _anthropic = null;
function getAnthropic() {
  if (!_anthropic) {
    _anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }
  return _anthropic;
}

let _firebaseReady = false;
function getDb() {
  if (!_firebaseReady) {
    const credentialsEnv =
      process.env.FIREBASE_CREDENTIALS_JSON ||
      process.env.GOOGLE_APPLICATION_CREDENTIALS;

    if (!credentialsEnv) {
      console.warn('⚠️  FIREBASE_CREDENTIALS_JSON no configurado');
      return null;
    }

    try {
      if (!admin.apps.length) {
        const parsed = JSON.parse(credentialsEnv);
        admin.initializeApp({ credential: admin.credential.cert(parsed) });
      }
      _firebaseReady = true;
    } catch (err) {
      console.error('❌ Error inicializando Firebase:', err.message);
      return null;
    }
  }

  return admin.firestore();
}

// ── Helpers ──────────────────────────────────────────────────────────────────

async function downloadImage(mediaUrl) {
  const response = await axios.get(mediaUrl, {
    auth: {
      username: process.env.TWILIO_ACCOUNT_SID,
      password: process.env.TWILIO_AUTH_TOKEN,
    },
    responseType: 'arraybuffer',
    timeout: 15000,
  });
  const contentType = response.headers['content-type'] || 'image/jpeg';
  const base64 = Buffer.from(response.data).toString('base64');
  return { base64, contentType };
}

async function extractInvoiceData(imageBase64, contentType) {
  const response = await getAnthropic().messages.create({
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
    const match = text.match(/\{[\s\S]*\}/);
    if (match) return JSON.parse(match[0]);
    throw new Error('Claude no devolvió JSON válido: ' + text);
  }
}

// ── Rutas ────────────────────────────────────────────────────────────────────

app.get('/', (req, res) => {
  res.json({ status: 'ok', service: 'La Delia - Facturas API' });
});

app.post('/webhook', async (req, res) => {
  const twiml = new twilio.twiml.MessagingResponse();

  try {
    console.log('🔔 WEBHOOK RECIBIDO');

    const from = req.body.From || '';
    const numMedia = parseInt(req.body.NumMedia || '0', 10);
    const mediaUrl = req.body.MediaUrl0;

    console.log(`📱 De: ${from} | Media: ${numMedia}`);

    if (numMedia === 0 || !mediaUrl) {
      twiml.message('👋 Hola! Enviá una foto de tu factura y la procesaremos automáticamente.');
      res.type('text/xml');
      return res.send(twiml.toString());
    }

    // Respuesta inmediata a Twilio (evita timeout de 15s)
    twiml.message('📥 Factura recibida! Estamos procesándola, un momento...');
    res.type('text/xml');
    res.send(twiml.toString());

    // Procesamiento async
    setImmediate(async () => {
      try {
        const { base64, contentType } = await downloadImage(mediaUrl);
        console.log('🖼️  Imagen descargada, enviando a Claude...');

        const invoiceData = await extractInvoiceData(base64, contentType);
        console.log('📊 Datos extraídos:', JSON.stringify(invoiceData));

        const db = getDb();
        let facturaId = null;

        if (db) {
          const docRef = await db.collection('facturas').add({
            ...invoiceData,
            phone: from.replace('whatsapp:', ''),
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

        await getTwilioClient().messages.create({
          from: `whatsapp:${process.env.TWILIO_PHONE}`,
          to: from,
          body: resumen,
        });

        console.log('📤 Resumen enviado al usuario');
      } catch (err) {
        console.error('❌ Error procesando factura:', err);
        try {
          await getTwilioClient().messages.create({
            from: `whatsapp:${process.env.TWILIO_PHONE}`,
            to: from,
            body: '❌ Hubo un error procesando tu factura. Intentá de nuevo o contactá al administrador.',
          });
        } catch (sendErr) {
          console.error('❌ Error enviando mensaje de error:', sendErr.message);
        }
      }
    });
  } catch (error) {
    console.error('❌ Error en webhook:', error);
    twiml.message('❌ Error interno. Intentá de nuevo.');
    res.type('text/xml');
    res.send(twiml.toString());
  }
});

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
      await getTwilioClient().messages.create({
        from: `whatsapp:${process.env.TWILIO_PHONE}`,
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
        : `❌ Tu factura ${data.numero_factura || facturaId} fue *rechazada*. Contactá al administrador.`;

      await getTwilioClient().messages.create({
        from: `whatsapp:${process.env.TWILIO_PHONE}`,
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
