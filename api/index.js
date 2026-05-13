const express = require('express');
const bodyParser = require('body-parser');
const twilio = require('twilio');
require('dotenv').config();

const app = express();

// Middlewares
app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());

// Inicializar cliente Twilio
const accountSid = process.env.TWILIO_ACCOUNT_SID;
const authToken = process.env.TWILIO_AUTH_TOKEN;
const twilioPhone = process.env.TWILIO_PHONE;

const client = twilio(accountSid, authToken);

// Health check
app.get('/', (req, res) => {
  res.json({ status: 'ok', service: 'La Delia - Facturas API' });
});

// Webhook para recibir mensajes de Twilio
app.post('/webhook', async (req, res) => {
  try {
    console.log('🔔 WEBHOOK RECIBIDO');
    
    const from = req.body.From;
    const body = req.body.Body;
    const mediaUrl = req.body.MediaUrl0;
    
    console.log(`📱 De: ${from}`);
    console.log(`💬 Mensaje: ${body}`);
    console.log(`🖼️ Media: ${Boolean(mediaUrl)}`);
    
    const phoneClean = from.replace('whatsapp:', '');
    
    // Crear respuesta TwiML
    const twiml = new twilio.twiml.MessagingResponse();
    twiml.message('✅ Factura recibida! Estamos procesándola...');
    
    console.log(`✅ Respuesta TwiML enviada`);
    
    res.type('text/xml');
    res.send(twiml.toString());
    
  } catch (error) {
    console.error('❌ Error:', error);
    
    const twiml = new twilio.twiml.MessagingResponse();
    twiml.message('❌ Error procesando tu mensaje');
    
    res.type('text/xml');
    res.send(twiml.toString());
  }
});

// Exportar para Vercel
module.exports = app;

// Para ejecutar localmente
const PORT = process.env.PORT || 3000;
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`🚀 Servidor corriendo en puerto ${PORT}`);
  });
}
