# 🛠️ GUÍA DE INSTALACIÓN PASO A PASO
## JJGT · Módulo de Pagos — Terminal de Transportes

---

## ⚡ Instalación Exprés (5 minutos)

```bash
# 1. Tener Python 3.10+ instalado
python --version

# 2. Ir a la carpeta del proyecto
cd jjgt-pagos

# 3. Instalar dependencias
pip install streamlit pandas "qrcode[pil]" Pillow reportlab pytz openpyxl requests plotly

# 4. Ejecutar
streamlit run pagos.py
```

¡Listo! Abre `http://localhost:8501` en el navegador.

---

## 📋 Requisitos del Sistema

| Componente | Mínimo | Recomendado |
|---|---|---|
| **Python** | 3.9 | 3.11 o 3.12 |
| **RAM** | 512 MB | 2 GB |
| **Disco** | 500 MB | 2 GB |
| **Pantalla** | 1280×720 | 1920×1080 táctil |
| **Conexión** | Solo para Google Drive sync | WiFi o Ethernet estable |
| **Sistema Operativo** | Windows 10, Ubuntu 20.04, macOS 12 | Ubuntu 22.04 LTS |

---

## 🪟 Instalación en Windows

### Paso 1 — Instalar Python
1. Ir a [python.org/downloads](https://www.python.org/downloads/)
2. Descargar Python 3.11 o 3.12
3. **Importante:** marcar ✅ "Add Python to PATH" durante la instalación
4. Verificar en CMD: `python --version`

### Paso 2 — Descargar el proyecto
```cmd
:: Opción A — Con Git
git clone https://github.com/tu-usuario/jjgt-pagos.git
cd jjgt-pagos

:: Opción B — Descargar ZIP y descomprimir en C:\jjgt-pagos
cd C:\jjgt-pagos
```

### Paso 3 — Crear entorno virtual
```cmd
python -m venv venv
venv\Scripts\activate
:: Verás (venv) al inicio de la línea de comandos
```

### Paso 4 — Instalar dependencias
```cmd
pip install -r requirements.txt
```

### Paso 5 — Ejecutar la aplicación
```cmd
streamlit run pagos.py
```

### Paso 6 — Configurar inicio automático (Windows)
Para que la app inicie al encender el equipo:
1. Crear archivo `iniciar_jjgt.bat`:
```bat
@echo off
cd C:\jjgt-pagos
call venv\Scripts\activate
streamlit run pagos.py --server.headless true
```
2. Presionar `Win + R` → escribir `shell:startup`
3. Copiar el archivo `.bat` en esa carpeta

---

## 🐧 Instalación en Ubuntu/Linux

### Paso 1 — Actualizar sistema e instalar Python
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git -y
python3 --version
```

### Paso 2 — Clonar o descargar el proyecto
```bash
git clone https://github.com/tu-usuario/jjgt-pagos.git
# O copiar manualmente los archivos
cd jjgt-pagos
```

### Paso 3 — Crear entorno virtual
```bash
python3 -m venv venv
source venv/bin/activate
```

### Paso 4 — Instalar dependencias
```bash
pip install -r requirements.txt
```

### Paso 5 — Ejecutar la aplicación
```bash
streamlit run pagos.py
```

### Paso 6 — Instalar como servicio systemd (producción)
```bash
# Crear archivo de servicio
sudo nano /etc/systemd/system/jjgt-pagos.service
```

Contenido del archivo:
```ini
[Unit]
Description=JJGT Módulo de Pagos — Terminal de Transportes
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=5
User=tu_usuario
WorkingDirectory=/home/tu_usuario/jjgt-pagos
Environment="PATH=/home/tu_usuario/jjgt-pagos/venv/bin"
ExecStart=/home/tu_usuario/jjgt-pagos/venv/bin/streamlit run pagos.py --server.port=8501 --server.headless=true --server.runOnSave=false
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# Habilitar e iniciar el servicio
sudo systemctl daemon-reload
sudo systemctl enable jjgt-pagos
sudo systemctl start jjgt-pagos

# Verificar que está corriendo
sudo systemctl status jjgt-pagos

# Ver logs en tiempo real
sudo journalctl -u jjgt-pagos -f
```

---

## 🍎 Instalación en macOS

### Paso 1 — Instalar Homebrew y Python
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.11
python3 --version
```

### Paso 2 — Instalar el proyecto
```bash
git clone https://github.com/tu-usuario/jjgt-pagos.git
cd jjgt-pagos
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run pagos.py
```

---

## 🖥️ Configuración de Kiosco Táctil

### Chromium en modo kiosco (Linux)
```bash
# Instalar Chromium
sudo apt install chromium-browser -y

# Crear script de inicio del kiosco
nano ~/iniciar_kiosco.sh
```

```bash
#!/bin/bash
# Esperar a que Streamlit esté listo
sleep 10

# Deshabilitar salvapantallas
xset s off
xset -dpms

# Abrir en modo kiosco
chromium-browser \
  --kiosk \
  --app=http://localhost:8501 \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-restore-session-state \
  --no-first-run \
  --start-maximized \
  --disable-pinch \
  --overscroll-history-navigation=0
```

```bash
chmod +x ~/iniciar_kiosco.sh
```

### Configuración de pantalla táctil
```bash
# Instalar drivers táctiles (ajustar según hardware)
sudo apt install xserver-xorg-input-evdev -y

# Calibrar pantalla táctil si es necesario
sudo apt install xinput-calibrator -y
xinput_calibrator
```

---

## ☁️ Configuración de Google Drive

### Paso 1 — Google Cloud Console
1. Ir a [console.cloud.google.com](https://console.cloud.google.com)
2. Crear nuevo proyecto: `jjgt-pagos-terminal`
3. En "APIs y servicios" → "Habilitar APIs":
   - ✅ Google Sheets API
   - ✅ Google Drive API

### Paso 2 — Crear Service Account
1. IAM y administración → Cuentas de servicio
2. "Crear cuenta de servicio"
   - Nombre: `jjgt-pagos-sync`
   - ID: `jjgt-pagos-sync`
3. Rol: "Editor"
4. En la cuenta creada → "Claves" → "Agregar clave" → JSON
5. Descargar el JSON → renombrar a `credentials.json`
6. Copiar a la carpeta del proyecto

### Paso 3 — Configurar en la app
1. Abrir la app → Panel Operador (PIN: 1234)
2. Módulo "☁️ Google Drive"
3. Subir `credentials.json` con el file uploader
4. Opcional: pegar el ID de un spreadsheet existente
5. Clic "🔗 Probar conexión" → debe mostrar "✅ Conectado"
6. Clic "📋 Crear/verificar estructura" → crea las 8 hojas

### Paso 4 — Verificar sincronización
1. En el Panel Operador → "☁️ Sincronizar todo ahora"
2. Verificar en Google Drive que el archivo `jjgt_pagos` tiene las 8 hojas con datos

---

## 🔗 Integración con facturacion.py

```bash
# Asegurarse de que ambos archivos están en la misma carpeta
ls -la
# Debe mostrar: pagos.py  facturacion.py

# Ejecutar el módulo de facturación en otra terminal (opcional)
streamlit run facturacion.py --server.port=8502
# Acceder en: http://localhost:8502
```

La integración es automática — ambos módulos usan la misma BD `terminal_descanso.db`.

---

## 🔑 Primeros Pasos Después de Instalar

### 1. Cambiar PINs de seguridad
```
Panel Operador (PIN: 1234) → ⚙️ Configuración → 👤 Operadores → Cambiar PIN
```
> ⚠️ **Obligatorio** antes de poner en producción

### 2. Configurar datos del negocio
```
Panel Operador → ⚙️ Configuración → 🏢 Negocio
```
- Nombre de la empresa
- NIT
- Dirección en la terminal
- Teléfono

### 3. Configurar datos de pago
```
Panel Operador → ⚙️ Configuración → 💰 Pagos
```
- Número Nequi del negocio
- Número Daviplata del negocio
- Cuenta bancaria para transferencias
- Link de MercadoPago
- WhatsApp del operador

### 4. Verificar tarifas
```
Panel Operador → ⚙️ Configuración → 🛏️ Tarifas
```
Ajustar precios por hora según la tarifa real del negocio.

### 5. Configurar WiFi de cada cubículo
```
Panel Operador → 🛏️ Cubículos → Expandir cubículo → Cambiar WiFi
```

---

## 🆘 Resolución de Problemas

### La app no abre
```bash
# Verificar que Streamlit está instalado
streamlit --version

# Verificar que estás en el entorno virtual correcto
which python  # debe mostrar la ruta del venv

# Ejecutar con más logs
streamlit run pagos.py --logger.level=debug
```

### Error: "ModuleNotFoundError"
```bash
# Reinstalar todas las dependencias
pip install -r requirements.txt --force-reinstall
```

### Los QR no se muestran
```bash
pip install "qrcode[pil]" Pillow --force-reinstall
```

### Error al generar PDF
```bash
pip install reportlab --force-reinstall
```

### La base de datos está corrupta
```bash
# CUIDADO: se perderán todos los datos
rm terminal_descanso.db
# La BD se recrea al reiniciar la app
streamlit run pagos.py
```

### No se puede conectar a Google Drive
- Verificar que `credentials.json` existe en la carpeta del proyecto
- Verificar que las APIs están habilitadas en Google Cloud Console
- Verificar que el Service Account tiene permiso de Editor
- Verificar conexión a internet

### La pantalla táctil no responde correctamente
```bash
# Verificar que el driver táctil está activo
xinput list

# Si el touch está invertido
xinput set-prop "Touch Device" "Coordinate Transformation Matrix" -1 0 1 0 -1 1 0 0 1
```

---

## 📞 Soporte

**Sistema:** JJGT · Módulo de Pagos  
**Versión:** 1.0.0  
**Tecnología:** Python + Streamlit

Para reportar problemas: describir el error, el sistema operativo, la versión de Python y los pasos para reproducirlo.

---

*JJGT · Guía de Instalación v1.0.0*
