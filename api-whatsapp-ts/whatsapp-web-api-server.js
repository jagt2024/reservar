import express from 'express';
import http from 'http';
import { Server as SocketServer } from 'socket.io';
import { Client, LocalAuth } from "whatsapp-web.js";
import { image as imageQr } from "qr-image";
import fs from 'fs';
import path from 'path';

const app = express();
const server = http.createServer(app);
const io = new SocketServer(server);

class WsTransporter extends Client {
  private status = false;

  constructor() {
    super({
      authStrategy: new LocalAuth(),
      puppeteer: {
        headless: true,
        args: [
          "--disable-setuid-sandbox",
          "--unhandled-rejections=strict",
        ],
      },
    });

    console.log("Iniciando....");

    this.initialize();

    this.on("ready", () => {
      this.status = true;
      console.log("LOGIN_SUCCESS");
      io.emit('ready');
    });

    this.on("auth_failure", () => {
      this.status = false;
      console.log("LOGIN_FAIL");
      io.emit('auth_failure');
    });

    this.on("qr", (qr) => {
      console.log("Nuevo código QR generado");
      this.generateImage(qr);
      io.emit('qr', qr);
    });
  }

  async sendMsg(lead: { message: string; phone: string }): Promise<any> {
    try {
      if (!this.status) return Promise.resolve({ error: "WAIT_LOGIN" });
      const { message, phone } = lead;
      const response = await this.sendMessage(`${phone}@c.us`, message);
      return { id: response.id.id };
    } catch (e: any) {
      return Promise.resolve({ error: e.message });
    }
  }

  getStatus(): boolean {
    return this.status;
  }

  private generateImage = (base64: string) => {
    const path = `${process.cwd()}/tmp`;
    let qr_svg = imageQr(base64, { type: "svg", margin: 4 });
    qr_svg.pipe(fs.createWriteStream(`${path}/qr.svg`));
    console.log(`⚡ Recuerda que el QR se actualiza cada minuto ⚡'`);
    console.log(`⚡ Actualiza F5 el navegador para mantener el mejor QR⚡`);
  };
}

const wsClient = new WsTransporter();

app.use(express.json());

app.get('/status', (req, res) => {
  res.json({ status: wsClient.getStatus() });
});

app.get('/qr', (req, res) => {
  const qrPath = path.join(process.cwd(), 'tmp', 'qr.svg');
  if (fs.existsSync(qrPath)) {
    res.sendFile(qrPath);
  } else {
    res.status(404).send('QR not generated yet');
  }
});

app.post('/send', async (req, res) => {
  const { message, phone } = req.body;
  const result = await wsClient.sendMsg({ message, phone });
  res.json(result);
});

const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
