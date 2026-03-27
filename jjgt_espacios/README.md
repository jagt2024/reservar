# 💤 JJGT · Módulo de Pagos — Kiosco Táctil 24/7
### Espacios de Descanso Personal · Terminal de Transportes

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-red?logo=streamlit)](https://streamlit.io)
[![SQLite](https://img.shields.io/badge/Base%20de%20datos-SQLite3-green?logo=sqlite)](https://sqlite.org)
[![Google Drive](https://img.shields.io/badge/Sync-Google%20Drive-yellow?logo=google-drive)](https://drive.google.com)
[![License](https://img.shields.io/badge/Licencia-Propietaria-orange)](LICENSE)

---

## 📋 Descripción General

**JJGT · Módulo de Pagos** es una aplicación completa de gestión de pagos y reservas construida con **Streamlit**, diseñada para operar como un **kiosco táctil self-service 24/7** al interior de una terminal de transportes.

Permite a los viajeros reservar cubículos de descanso individual, pagar con múltiples métodos colombianos (Nequi, Daviplata, PSE, MercadoPago, Efectivo, Transferencia), recibir su voucher con código de acceso y WiFi, y generar automáticamente la factura electrónica — todo sin intervención de un operador humano para pagos digitales.

### Características del negocio
| Atributo | Detalle |
|---|---|
| **Servicio** | Espacios de descanso en cubículos individuales |
| **Ubicación** | Interior de terminal de transportes |
| **Operación** | 24 horas / 7 días / 365 días |
| **Cobro** | Por hora o fracción (mínimo 30 minutos) |
| **Servicios incluidos** | Baño · WiFi alta velocidad · Carga USB/110V |
| **Clientes** | Viajeros de paso esperando su transporte |

---

## 🚀 Instalación Rápida

### 1. Clonar o descargar el proyecto
```bash
# Si usas Git
git clone https://github.com/tu-usuario/jjgt-pagos.git
cd jjgt-pagos

# O simplemente coloca pagos.py en una carpeta
```

### 2. Crear entorno virtual (recomendado)
```bash
python -m venv venv

# Activar en Linux/Mac
source venv/bin/activate

# Activar en Windows
venv\Scripts\activate
```

### 3. Instalar dependencias
```bash
# Instalación completa
pip install -r requirements.txt

# O instalación mínima (sin Google Drive)
pip install streamlit pandas "qrcode[pil]" Pillow reportlab pytz openpyxl requests plotly
```

### 4. Ejecutar la aplicación
```bash
streamlit run pagos.py
```

La app abrirá automáticamente en `http://localhost:8501`

---

## 📁 Estructura del Proyecto

```
jjgt-pagos/
│
├── pagos.py                    # 🎯 Aplicación principal (2.795 líneas)
├── facturacion.py              # 🧾 Módulo de facturación (BD compartida)
├── requirements.txt            # 📦 Dependencias Python
├── README.md                   # 📖 Este archivo
├── BRIEF.md                    # 📄 Brief técnico del proyecto
├── .streamlit/
│   └── config.toml             # ⚙️  Configuración de Streamlit
├── credentials.json            # 🔐 Google Service Account (NO subir a Git)
├── terminal_descanso.db        # 🗄️  Base de datos SQLite (generada auto.)
└── assets/
    └── logo.png                # 🖼️  Logo del negocio (opcional)
```

> ⚠️ **Importante:** Nunca subas `credentials.json` ni `terminal_descanso.db` a un repositorio público.

---

## 🖥️ Flujo de Usuario — Kiosco Táctil

```
┌─────────────────────────────────────────────────────────┐
│  PANTALLA 0 · Bienvenida                                │
│  Disponibilidad en tiempo real · Reloj Colombia         │
│  Botón "🛏️ RESERVAR MI ESPACIO"                        │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  PANTALLA 1 · Selección de Cubículo y Tiempo            │
│  Botones táctiles: 30min / 1h / 2h / 3h / 4h / Custom  │
│  Grid de 12 cubículos con estado y countdown            │
│  Precio calculado en tiempo real (madrugada/descuentos) │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  PANTALLA 2 · Datos del Cliente                         │
│  Nombre · Documento · Teléfono · Email (opcional)       │
│  Toggle: Factura a empresa                              │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  PANTALLA 3 · Pago                                      │
│  💚 Nequi · 💙 Daviplata · 💵 Efectivo                 │
│  📲 PSE · MercadoPago · Transferencia · Tarjeta         │
│  QR dinámico + Polling automático de confirmación       │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  PANTALLA 4 · Confirmación                              │
│  ✅ Animación de éxito · Cubículo activado              │
│  Código de acceso PIN enorme visible                    │
│  Factura generada automáticamente                       │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  PANTALLA 5 · Voucher                                   │
│  PIN · WiFi · Servicios · Total · Factura N°            │
│  📱 WhatsApp · 📄 PDF · 🖨️ Imprimir                    │
└─────────────────────────────────────────────────────────┘
```

---

## 💳 Métodos de Pago Soportados

| Método | Tipo | QR | Automático |
|---|---|---|---|
| **Nequi** | App billetera | ✅ Deep link | ✅ Polling |
| **Daviplata** | App billetera | ✅ Deep link | ✅ Polling |
| **Efectivo** | Presencial | ❌ | ❌ PIN operador |
| **PSE** | Débito bancario | ✅ URL | ❌ Manual |
| **MercadoPago** | App/Web | ✅ Link MP | ❌ Manual |
| **Transferencia** | Bancaria | ✅ Datos QR | ❌ PIN operador |
| **Tarjeta** | Datáfono físico | ❌ | ❌ Caja |

### Formatos QR por método
```
Nequi:         nequi://transfer?phone=NUM&amount=MONTO&description=REF
Daviplata:     daviplata://pay?to=NUM&amount=MONTO&ref=REF
MercadoPago:   https://mpago.la/LINK?external_reference=REF
PSE:           URL pasarela con referencia y monto
Transferencia: BANCO|TIPO|CUENTA|NIT|MONTO|REF
Multipasarela: PAGO|NEGOCIO|MONTO|REF|COP
```

---

## 🗄️ Base de Datos

La aplicación usa **SQLite3** (sin configuración adicional). La base de datos `terminal_descanso.db` se crea automáticamente al primer inicio y es **compartida** con `facturacion.py`.

### Tablas

#### Compartidas con `facturacion.py`
| Tabla | Descripción |
|---|---|
| `clientes` | Datos de viajeros / empresas |
| `facturas` | Facturas emitidas (FACT-YYYY-NNNN) |
| `factura_items` | Líneas de detalle de cada factura |

#### Propias del módulo de pagos
| Tabla | Descripción |
|---|---|
| `cubiculos` | Estado en tiempo real de 12 cubículos |
| `tarifas` | Estándar ($15.000/h) · Madrugada · Festivo |
| `reservas` | Historial completo de reservas |
| `pagos` | Registro de transacciones |
| `operadores` | Usuarios con PIN hasheado (SHA-256) |
| `configuracion_pagos` | Parámetros del sistema (key-value) |
| `sync_log` | Cola de sincronización con Google Drive |

### Datos de demostración precargados
- 12 cubículos (#01–#12): 5 libres · 5 ocupados · 2 en mantenimiento
- 3 tarifas: Estándar · Madrugada · Festivo
- 8 reservas completadas (mix de métodos de pago)
- 2 operadores: admin (PIN: **1234**) · cajero (PIN: **5678**)

> ⚠️ **Cambiar los PINs** antes de llevar a producción desde ⚙️ Configuración.

---

## 🔧 Panel de Operador

Acceso: botón **"👤 Operador"** en la pantalla de bienvenida → ingresar PIN.

| Módulo | Funcionalidad |
|---|---|
| 🏠 **Dashboard** | Estado en tiempo real · KPIs del turno · Alertas |
| 🛏️ **Cubículos** | Liberar · Mantenimiento · Cambiar WiFi |
| ⏳ **Pagos Pendientes** | Confirmar efectivo/transferencia con PIN |
| 📊 **Reportes** | Ingresos · Reservas · Gráfico métodos · Exportar CSV |
| ☁️ **Google Drive** | Configurar credenciales · Sincronizar `jjgt_pagos` |
| ⚙️ **Configuración** | Negocio · Tarifas · Datos de pago · Cambiar PIN |

---

## ☁️ Integración con Google Drive

El sistema sincroniza automáticamente con el archivo **`jjgt_pagos`** en Google Drive.

### Configuración paso a paso

1. **Crear proyecto en Google Cloud Console**
   - Ir a [console.cloud.google.com](https://console.cloud.google.com)
   - Crear nuevo proyecto: `jjgt-pagos`
   - Habilitar APIs: **Google Sheets API** y **Google Drive API**

2. **Crear Service Account**
   - IAM & Admin → Service Accounts → Crear cuenta
   - Rol: Editor
   - Descargar clave JSON → renombrar a `credentials.json`
   - Colocar en el mismo directorio que `pagos.py`

3. **Compartir el spreadsheet** (si ya existe)
   - Compartir con el email del Service Account (`...@...iam.gserviceaccount.com`)
   - Permiso: Editor

4. **Configurar en la app**
   - Abrir Panel Operador → ☁️ Google Drive
   - Subir `credentials.json`
   - Ingresar ID del spreadsheet (o dejar vacío para crear nuevo)
   - Clic en "🔗 Probar conexión"
   - Clic en "📋 Crear/verificar estructura"

### Hojas del archivo `jjgt_pagos`

| Hoja | Columnas | Actualización |
|---|---|---|
| `Reservas` | 25 cols: ID, N°, Fecha, Cubículo, Cliente... | Tiempo real |
| `Pagos` | 11 cols: monto, método, referencia... | Tiempo real |
| `Clientes` | 15 cols: datos + historial acumulado | Tiempo real |
| `Cubiculos_Estado` | 14 cols: estado actual en tiempo real | Cada cambio |
| `Facturas` | 21 cols: datos completos de facturación | Al emitir |
| `Dashboard_Diario` | 21 cols: resumen diario automático | Al cerrar reserva |
| `Tarifas_Config` | 11 cols: configuración de precios | Al cambiar |
| `Log_Operaciones` | 11 cols: auditoría completa | Cada operación |

---

## 🔗 Integración con `facturacion.py`

Ambos módulos comparten la **misma base de datos** `terminal_descanso.db`.

```python
# Al confirmar un pago, se ejecuta automáticamente:
numero_factura, factura_id = registrar_en_facturacion(reserva_data, cliente_data)
# → Crea registro en tabla `facturas` con número FACT-YYYY-NNNN
# → Crea ítem: "Espacio de descanso #XX · Xh · WiFi+Baño+Carga"
# → El número de factura aparece en el voucher del cliente
```

Para usar el módulo de facturación:
```bash
streamlit run facturacion.py  # En otra terminal o pestaña
```

---

## ⚙️ Configuración de Streamlit

Crear archivo `.streamlit/config.toml`:

```toml
[server]
port = 8501
headless = true
runOnSave = false
maxUploadSize = 10

[theme]
base = "dark"
primaryColor = "#00d4ff"
backgroundColor = "#050b1a"
secondaryBackgroundColor = "#0d1f3c"
textColor = "#e2e8f0"
font = "sans serif"

[browser]
gatherUsageStats = false
```

---

## 🚀 Despliegue en Producción

### Opción 1 — Servidor Linux (VPS / Terminal)
```bash
# Instalar dependencias del sistema
sudo apt update && sudo apt install python3-pip python3-venv -y

# Configurar el proyecto
git clone https://github.com/tu-usuario/jjgt-pagos.git
cd jjgt-pagos
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Ejecutar como servicio con systemd
sudo nano /etc/systemd/system/jjgt-pagos.service
```

```ini
[Unit]
Description=JJGT Módulo de Pagos
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/jjgt-pagos
Environment="PATH=/home/ubuntu/jjgt-pagos/venv/bin"
ExecStart=/home/ubuntu/jjgt-pagos/venv/bin/streamlit run pagos.py --server.port=8501 --server.headless=true
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable jjgt-pagos
sudo systemctl start jjgt-pagos
```

### Opción 2 — Kiosco táctil (Raspberry Pi / Mini PC)
```bash
# Instalar en modo quiosco con Chromium
chromium-browser --kiosk --app=http://localhost:8501 --noerrdialogs --disable-infobars
```

### Opción 3 — Streamlit Community Cloud
1. Subir código a GitHub (sin `credentials.json` ni `.db`)
2. Ir a [share.streamlit.io](https://share.streamlit.io)
3. Conectar repo y desplegar
4. Configurar Secrets para las credenciales de Google

---

## 🔐 Seguridad

| Aspecto | Implementación |
|---|---|
| **PINs de operador** | SHA-256 hasheado (nunca en texto plano) |
| **Credenciales Google** | Archivo local `credentials.json` (no en código) |
| **BD SQLite** | Solo lectura/escritura local, sin exposición en red |
| **Datos del cliente** | Solo nombre, documento, teléfono, email |
| **Claves WiFi** | Solo visibles tras pago confirmado |

**Recomendaciones de producción:**
- Cambiar PINs por defecto (`1234`, `5678`) antes del primer uso
- Usar HTTPS con certificado SSL si se expone a internet
- Hacer backups diarios de `terminal_descanso.db`
- No subir `credentials.json` a Git (añadir a `.gitignore`)

---

## 📦 Dependencias Principales

| Paquete | Versión | Uso |
|---|---|---|
| `streamlit` | ≥1.35 | Framework de la aplicación |
| `pandas` | ≥2.0 | Manejo de datos y tablas |
| `qrcode[pil]` | ≥7.4 | Generación de códigos QR |
| `Pillow` | ≥10.0 | Procesamiento de imágenes |
| `reportlab` | ≥4.0 | Generación de PDF térmico |
| `pytz` | ≥2024 | Zona horaria Colombia |
| `openpyxl` | ≥3.1 | Exportación Excel |
| `plotly` | ≥5.18 | Gráficas en panel operador |
| `gspread` | ≥6.0 | Integración Google Sheets |
| `google-auth` | ≥2.28 | Autenticación Google Drive |

---

## 🆘 Solución de Problemas

### La app no inicia
```bash
# Verificar versión de Python
python --version  # debe ser 3.10+

# Reinstalar dependencias
pip install -r requirements.txt --force-reinstall
```

### Los QR no se generan
```bash
pip install "qrcode[pil]" Pillow --force-reinstall
```

### Error de Google Drive
- Verificar que `credentials.json` está en el directorio del proyecto
- Verificar que las APIs de Google Sheets y Drive están habilitadas
- Verificar que el Service Account tiene permiso de Editor en el spreadsheet

### La base de datos está corrupta
```bash
# Eliminar y recrear (se pierden los datos)
rm terminal_descanso.db
streamlit run pagos.py  # La recrea automáticamente
```

### El PDF no se genera
```bash
pip install reportlab --force-reinstall
```

---

## 📊 Tarifas por Defecto

| Tarifa | Precio/hora | Horario | Descuento 3h+ | Descuento 6h+ |
|---|---|---|---|---|
| **Estándar** | $15.000 COP | 06:00 – 23:59 | 10% | 20% |
| **Madrugada** | $10.000 COP | 00:00 – 05:59 | 10% | 20% |
| **Festivo** | $18.000 COP | Días festivos | 10% | 20% |

> Las tarifas son configurables desde el Panel de Operador → ⚙️ Configuración → 🛏️ Tarifas

---

## 📞 Soporte y Contacto

**Proyecto:** JJGT · Espacios de Descanso Personal  
**Ubicación:** Terminal de Transportes  
**Módulo:** Sistema de Pagos y Reservas  
**Versión:** 1.0.0  
**Desarrollado con:** Python + Streamlit + SQLite + Google Drive  

---

## 📄 Licencia

Proyecto propietario — JJGT · Todos los derechos reservados.  
No se permite la redistribución sin autorización escrita del titular.

---

*Generado con ❤️ · JJGT · Módulo de Pagos v1.0.0*
