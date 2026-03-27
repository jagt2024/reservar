# 📄 BRIEF TÉCNICO Y DE NEGOCIO
## JJGT · Módulo de Pagos — Espacios de Descanso en Terminal de Transportes

---

## 1. RESUMEN EJECUTIVO

| Campo | Detalle |
|---|---|
| **Proyecto** | Módulo de Pagos y Reservas — Kiosco Táctil 24/7 |
| **Cliente / Propietario** | JJGT |
| **Negocio** | Espacios de descanso personal en cubículos individuales |
| **Ubicación** | Interior de terminal de transportes |
| **Versión** | 1.0.0 |
| **Fecha de creación** | 2025 |
| **Stack tecnológico** | Python · Streamlit · SQLite3 · Google Drive |
| **Archivo principal** | `pagos.py` (2.795 líneas) |

---

## 2. DESCRIPCIÓN DEL NEGOCIO

### 2.1 Concepto
JJGT ofrece **espacios de descanso personal en cubículos individuales** ubicados al interior de una terminal de transportes. Los viajeros que esperan la salida de su transporte pueden acceder a un espacio privado con todas las comodidades necesarias para descansar, trabajar o cargar sus dispositivos.

### 2.2 Propuesta de Valor
> *"Tu espacio de descanso en la terminal — privado, seguro y equipado"*

- **Privacidad** en un cubículo individual, alejado del bullicio de la terminal
- **Conectividad** con WiFi de alta velocidad incluido
- **Carga de dispositivos** con puertos USB y corriente 110V
- **Higiene** con acceso a baño privado o compartido
- **Flexibilidad** de pago por hora (mínimo 30 minutos)
- **Autoservicio** sin necesidad de interacción humana

### 2.3 Modelo de Negocio
| Elemento | Detalle |
|---|---|
| **Tipo de servicio** | Alquiler de espacio por tiempo |
| **Unidad de cobro** | Por hora o fracción (mínimo 30 min) |
| **Tarifa base** | $15.000 COP/hora |
| **Tarifa madrugada** | $10.000 COP/hora (00:00–06:00) |
| **Tarifa festivo** | $18.000 COP/hora |
| **Descuento 3h+** | 10% del total |
| **Descuento 6h+** | 20% del total |
| **IVA** | 19% (incluido en el precio mostrado) |
| **Capacidad** | 12 cubículos simultáneos |
| **Operación** | 24h / 7d / 365d |

### 2.4 Servicios Incluidos en Cada Cubículo
- 🚿 Baño privado o compartido
- 🌐 WiFi de alta velocidad (red y contraseña únicas por cubículo)
- 🔌 Puertos de carga USB (5V/2A)
- 🔌 Toma de corriente 110V (portátil, tableta)
- 💤 Espacio confortable de descanso

---

## 3. OBJETIVO DEL SOFTWARE

### 3.1 Objetivo Principal
Desarrollar una aplicación de **kiosco táctil self-service** que permita a los viajeros realizar de forma completamente autónoma todo el proceso de reserva y pago de un cubículo de descanso, desde la selección hasta la emisión del voucher con código de acceso y factura electrónica.

### 3.2 Objetivos Específicos
1. Eliminar la necesidad de personal para cobros con métodos de pago digital
2. Aceptar los principales métodos de pago digitales colombianos (Nequi, Daviplata, PSE, MercadoPago)
3. Generar automáticamente la factura y el ticket de acceso al confirmar el pago
4. Sincronizar todos los datos con Google Drive para acceso remoto del propietario
5. Integrarse con el módulo de facturación existente (`facturacion.py`)
6. Proveer un panel de control al operador para gestión en tiempo real

### 3.3 Alcance del Proyecto
**Incluye:**
- Flujo completo de reserva y pago (6 pantallas)
- Integración con 7 métodos de pago
- Generación de QR para pagos digitales
- Generación de PDF (ticket térmico 80mm)
- Panel de operador con 6 módulos
- Base de datos SQLite compartida con `facturacion.py`
- Sincronización con Google Drive (`jjgt_pagos` — 8 hojas)
- Temporizadores en tiempo real por cubículo

**No incluye (versión 1.0):**
- Integración real con APIs de Nequi/Daviplata (webhooks de confirmación automática)
- Sistema de reservas anticipadas (solo walk-in)
- App móvil nativa (solo web/kiosco)
- Control de acceso físico electrónico (cerradura inteligente)
- CMS de contenido para la pantalla de bienvenida

---

## 4. ARQUITECTURA TÉCNICA

### 4.1 Stack Tecnológico

```
┌────────────────────────────────────────────────────────────────┐
│                      CAPA DE PRESENTACIÓN                      │
│  Streamlit 1.35+ · CSS personalizado · JavaScript inject      │
│  Modo kiosco táctil · Modo escritorio operador                 │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                      CAPA DE NEGOCIO                           │
│  pagos.py (Python 3.10+)                                       │
│  • Cálculo de tarifas y descuentos                             │
│  • Gestión de estados de cubículos                             │
│  • Generación de QR (qrcode + Pillow)                         │
│  • Generación de PDF (ReportLab)                               │
│  • Integración con facturacion.py                              │
│  • Sincronización Google Drive (gspread)                       │
└────────────────────────┬───────────────┬───────────────────────┘
                         │               │
┌────────────────────────▼──┐   ┌────────▼───────────────────────┐
│     BASE DE DATOS LOCAL   │   │      GOOGLE DRIVE              │
│  SQLite3                  │   │  Archivo: jjgt_pagos           │
│  terminal_descanso.db     │   │  8 hojas · Sync en tiempo real │
│  Tablas compartidas con   │   │  Reservas · Pagos · Clientes   │
│  facturacion.py           │   │  Cubículos · Facturas          │
│                           │   │  Dashboard · Tarifas · Log     │
└───────────────────────────┘   └────────────────────────────────┘
```

### 4.2 Módulos del Sistema

```
pagos.py
├── CONFIGURACIÓN Y CSS (modo kiosco táctil)
├── BASE DE DATOS (init_db, CRUD, seed data)
├── FUNCIONES DE NEGOCIO
│   ├── calcular_precio()         Tarifas + descuentos
│   ├── get_cubiculos()           Estado en tiempo real
│   ├── activar_cubiculo()        Al confirmar pago
│   ├── liberar_cubiculo()        Al vencer o cancelar
│   └── generar_codigo_acceso()   PIN de 4 dígitos
├── GENERACIÓN DE QR
│   ├── generar_qr_b64()          QR como base64 PNG
│   └── qr_data_para_metodo()     Deep links por plataforma
├── INTEGRACIÓN FACTURACIÓN
│   ├── registrar_en_facturacion() BD compartida
│   └── crear_reserva_completa()   Flujo completo
├── GOOGLE DRIVE
│   ├── init_google_drive()        Autenticación + hojas
│   ├── _drive_sync_background()   Sync automático
│   └── sincronizacion_completa()  Export total SQLite→Drive
├── GENERACIÓN DE PDF
│   ├── generar_ticket_pdf()       Ticket térmico 80mm
│   └── voucher_html()             Voucher descargable HTML
├── PANTALLAS CLIENTE (6 pantallas)
│   ├── show_bienvenida()
│   ├── show_seleccion()
│   ├── show_datos()
│   ├── show_pago()                Tabs por método
│   ├── show_confirmacion()
│   └── show_voucher()
├── PANEL OPERADOR (6 módulos)
│   ├── show_operador_login()
│   ├── _op_dashboard()
│   ├── _op_cubiculos()
│   ├── _op_pagos_pendientes()
│   ├── _op_reportes()
│   ├── _op_google_drive()
│   └── _op_configuracion()
└── MAIN() — Router principal
```

### 4.3 Diagrama de Base de Datos

```
clientes ──────────────── reservas ──────── pagos
    │                         │
    │                    cubiculos
    │                         │
    └──── facturas ────── factura_items
              │
         configuracion_pagos
         operadores
         tarifas
         sync_log
```

### 4.4 Flujo de Datos — Confirmación de Pago

```
Cliente selecciona cubículo + tiempo
        ↓
Ingresa datos personales
        ↓
Elige método de pago
        ↓
Se genera QR dinámico con deep link
        ↓
Cliente realiza el pago en su app
        ↓
┌───────────────────────────────────┐
│ ¿Pago digital (Nequi/Daviplata)?  │
│ → Polling automático c/5 seg      │
│ ¿Efectivo/Transferencia?          │
│ → PIN del operador                │
└───────────────────────────────────┘
        ↓
Confirmar pago
        ↓
crear_reserva_completa()
├── Inserta en tabla reservas
├── Inserta en tabla pagos
├── Inserta cliente (si nuevo)
├── registrar_en_facturacion()
│   ├── Genera FACT-YYYY-NNNN
│   ├── Inserta en facturas
│   └── Inserta en factura_items
├── activar_cubiculo() → estado = 'ocupado'
└── _drive_sync_background() → Google Drive
        ↓
Muestra voucher con:
- N° Reserva · N° Factura
- Cubículo · PIN de acceso
- WiFi (SSID + Password)
- Total · Método de pago
        ↓
Cliente descarga/comparte voucher
        ↓
Cliente va a su cubículo con el PIN
```

---

## 5. DISEÑO Y EXPERIENCIA DE USUARIO

### 5.1 Principios de Diseño
El diseño sigue el concepto **"Noche de viaje"**: un espacio tecnológico, tranquilo y confiable que evoca el descanso en tránsito.

| Principio | Aplicación |
|---|---|
| **Táctil prioritario** | Botones mínimo 72px–88px de altura |
| **Visibilidad extrema** | Números de cubículo legibles a 1 metro |
| **Mínimo de pasos** | Solo 4 campos obligatorios para el cliente |
| **Feedback inmediato** | Animaciones de confirmación claras |
| **Inclusivo** | Letras grandes, lenguaje simple, sin jerga técnica |

### 5.2 Paleta de Colores

| Color | Hex | Uso |
|---|---|---|
| Fondo profundo | `#050b1a` | Background principal |
| Fondo tarjetas | `#0d1f3c` | Cards y contenedores |
| Cyan principal | `#00d4ff` | Acciones, QR, métricas |
| Verde neón | `#00ff88` | Éxito, libre, confirmado |
| Rojo alerta | `#ff4757` | Ocupado, error, vencido |
| Amarillo | `#ffd32a` | Advertencia, por liberar |
| Violeta | `#a29bfe` | Mantenimiento, secundario |

### 5.3 Tipografías
- **Syne** (Google Fonts) — Títulos, navegación, botones, UI
- **Inconsolata** (Google Fonts) — Temporizadores, códigos PIN, precios, números

### 5.4 Patrones de Interacción
- **Kiosco táctil**: todos los botones ≥80px, sin hover-only interactions
- **Retroalimentación visual**: animaciones CSS en cada acción importante
- **Estados claros**: código de colores consistente en todos los cubículos
- **Progreso visible**: stepper de 5 pasos siempre visible durante el flujo
- **Sin callejones sin salida**: botón "← Volver" en cada pantalla

---

## 6. SEGURIDAD

### 6.1 Autenticación
- PINs de operador hasheados con **SHA-256** (nunca almacenados en texto plano)
- Máximo 3 intentos fallidos en login de operador
- PIN de 4–8 dígitos configurable por el administrador

### 6.2 Datos del Cliente
- Se recopilan solo los datos mínimos necesarios para la factura
- Sin almacenamiento de datos bancarios ni tokens de pago
- Los códigos QR de pago se generan en el dispositivo (sin servidor intermedio)

### 6.3 Google Drive
- Autenticación via Service Account (credenciales en archivo local, nunca en código)
- Archivo `credentials.json` debe excluirse de control de versiones (`.gitignore`)

### 6.4 Recomendaciones para Producción
1. Cambiar PINs por defecto (admin: 1234, cajero: 5678) antes del primer uso
2. Usar HTTPS si la app se expone a internet
3. Hacer backup diario de `terminal_descanso.db`
4. Restringir acceso físico al equipo del kiosco
5. Usar usuario de sistema con permisos limitados para ejecutar la app

---

## 7. INTEGRACIÓN CON MÓDULO DE FACTURACIÓN

### 7.1 Estrategia
Ambos módulos comparten la misma base de datos SQLite (`terminal_descanso.db`). La integración es **directa a nivel de BD** sin APIs intermedias.

### 7.2 Contrato de Datos

```python
# Datos que pagos.py escribe en la BD para facturacion.py
factura = {
    "numero":          "FACT-2025-0087",       # str
    "tipo":            "Factura de Venta",      # str
    "fecha_emision":   "2025-01-15",           # str YYYY-MM-DD
    "cliente_id":      42,                      # int FK clientes
    "subtotal":        26050.42,               # float
    "iva":             4949.58,                # float
    "total":           31000.00,               # float
    "estado":          "pagada",               # str
    "metodo_pago":     "Nequi",               # str
    "notas":           "Cubículo #05 · 2h · WiFi+Baño+Carga"
}
```

### 7.3 Numeración de Facturas
- Formato: `FACT-YYYY-NNNN` (configurable el prefijo)
- Contador secuencial global en tabla `configuracion_pagos`
- Garantía de unicidad: constraint UNIQUE en columna `numero`

---

## 8. GOOGLE DRIVE — DETALLE DE HOJAS `jjgt_pagos`

### Hoja 1: Reservas (25 columnas)
Registro completo de cada reserva con todos los datos del cliente, cubículo, tiempo, precio, método de pago, código de acceso y factura asociada.

### Hoja 2: Pagos (11 columnas)
Cada transacción de pago con su referencia externa, estado, quién la confirmó y tiempo de procesamiento.

### Hoja 3: Clientes (15 columnas)
Base de datos de viajeros con historial acumulado (total de visitas, total gastado, fechas de primera y última visita).

### Hoja 4: Cubiculos_Estado (14 columnas)
**Actualización en tiempo real** cada vez que cambia el estado de un cubículo. Permite monitoreo remoto de la ocupación.

### Hoja 5: Facturas (21 columnas)
Espejo de todas las facturas emitidas para contabilidad y declaración de IVA.

### Hoja 6: Dashboard_Diario (21 columnas)
Resumen automático por día: ingresos brutos/netos, IVA recaudado, distribución por método de pago, tasa de ocupación, hora pico, ticket promedio. **Ideal para seguimiento de KPIs del negocio.**

### Hoja 7: Tarifas_Config (11 columnas)
Configuración actual de tarifas para auditoría de cambios de precios.

### Hoja 8: Log_Operaciones (11 columnas)
Auditoría completa de cada operación del sistema: quién hizo qué, cuándo y con qué resultado. Incluye IP del dispositivo.

---

## 9. PLAN DE IMPLEMENTACIÓN

### Fase 1 — Instalación y configuración básica (Día 1)
- [ ] Instalar Python 3.10+ en el equipo del kiosco
- [ ] Crear entorno virtual e instalar dependencias
- [ ] Ejecutar `pagos.py` y verificar que carga correctamente
- [ ] Cambiar PINs por defecto (1234 → PIN seguro)
- [ ] Configurar datos del negocio (NIT, dirección, teléfono)
- [ ] Configurar números de pago (Nequi, Daviplata, cuenta bancaria)

### Fase 2 — Configuración de tarifas y cubículos (Día 1-2)
- [ ] Ajustar tarifas al precio real del negocio
- [ ] Configurar WiFi SSID y password de cada cubículo
- [ ] Verificar que los 12 cubículos están correctamente registrados
- [ ] Probar flujo completo de reserva con método Efectivo

### Fase 3 — Integración Google Drive (Día 2-3)
- [ ] Crear proyecto en Google Cloud Console
- [ ] Generar y descargar `credentials.json`
- [ ] Configurar en Panel Operador → Google Drive
- [ ] Verificar que se crean las 8 hojas en `jjgt_pagos`
- [ ] Probar sincronización manual completa

### Fase 4 — Integración con facturacion.py (Día 3)
- [ ] Colocar `facturacion.py` en el mismo directorio
- [ ] Verificar que comparten `terminal_descanso.db`
- [ ] Verificar que las facturas aparecen en el módulo de facturación
- [ ] Configurar numeración de facturas (prefijo, número inicial)

### Fase 5 — Pruebas completas (Día 4-5)
- [ ] Prueba completa con Nequi (QR + confirmación manual)
- [ ] Prueba completa con Daviplata
- [ ] Prueba completa con Efectivo (PIN operador)
- [ ] Prueba de generación de PDF del ticket
- [ ] Prueba de temporizadores y alertas
- [ ] Prueba del panel de operador completo
- [ ] Prueba de extensión de tiempo
- [ ] Prueba de liberación anticipada de cubículo

### Fase 6 — Modo producción (Día 5-7)
- [ ] Configurar autoarranque del servicio (systemd)
- [ ] Configurar modo kiosco en el navegador
- [ ] Ajustar tamaño de pantalla según el hardware
- [ ] Capacitar al personal operador (PIN, confirmar pagos, reportes)
- [ ] Activar backup automático de la BD

---

## 10. LIMITACIONES CONOCIDAS (v1.0)

| Limitación | Impacto | Solución futura |
|---|---|---|
| Confirmación de Nequi/Daviplata es manual | El cliente debe presionar "Ya pagué" | Webhook oficial de las pasarelas |
| Sin control de acceso físico | El operador debe abrir físicamente | Integrar cerradura inteligente con API |
| Sin reservas anticipadas | Solo walk-in en el momento | Módulo de reservas con calendario |
| Temporizadores vía polling | No es push real-time | WebSocket o SSE |
| Sin multimoneda real | Solo COP | Integrar FX para turistas extranjeros |
| Google Drive requiere internet | Sin sync si no hay red | Ya solucionado con cola `sync_log` |

---

## 11. MÉTRICAS DE ÉXITO

| KPI | Meta | Medición |
|---|---|---|
| Tasa de ocupación | ≥ 70% horas pico | Dashboard diario en Drive |
| Transacciones digitales | ≥ 60% (vs efectivo) | Hoja Pagos en Drive |
| Tiempo promedio de checkout | < 3 minutos | Log de operaciones |
| Incidencias técnicas | < 2 por semana | Log de errores |
| Ingresos por cubículo/día | > $120.000 COP | Dashboard diario |
| NPS clientes | ≥ 4.0/5.0 | Encuesta futura |

---

## 12. HISTORIAL DE VERSIONES

| Versión | Fecha | Cambios |
|---|---|---|
| 1.0.0 | 2025 | Versión inicial completa |

---

*JJGT · Módulo de Pagos · Brief Técnico y de Negocio v1.0.0*
