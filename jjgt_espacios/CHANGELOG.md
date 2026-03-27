# 📋 CHANGELOG
## JJGT · Módulo de Pagos — Historial de Cambios

Todos los cambios notables de este proyecto serán documentados en este archivo.  
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).

---

## [1.0.0] — 2025

### ✨ Agregado (primera versión)

#### Flujo Cliente — Kiosco Táctil
- Pantalla 0: Bienvenida con disponibilidad en tiempo real y animación de estrellas CSS
- Pantalla 1: Selección de cubículo y tiempo con cálculo de precio en tiempo real
- Pantalla 2: Captura de datos del cliente (mínimo de campos para viajeros de paso)
- Pantalla 3: Selección de método de pago (7 métodos)
- Pantalla 4: Confirmación de pago con código de acceso PIN
- Pantalla 5: Voucher completo con descarga PDF y envío WhatsApp

#### Métodos de Pago
- Nequi: QR deep link `nequi://transfer` + polling de confirmación
- Daviplata: QR deep link `daviplata://pay` + polling de confirmación
- Efectivo: Flujo de llamada al operador + confirmación con PIN
- PSE: QR URL con referencia de pago
- MercadoPago: QR link de cobro configurable
- Transferencia bancaria: Datos + QR con info bancaria
- Tarjeta: Redirección a datáfono físico

#### Generación de QR
- QR dinámico por método de pago con colores corporativos
- QR multipasarela unificado
- Descarga PNG del QR desde la interfaz

#### Panel de Operador
- Dashboard: estado en tiempo real de 12 cubículos, KPIs del turno
- Gestión de cubículos: liberar, mantenimiento, cambiar WiFi
- Pagos pendientes: confirmar o rechazar con PIN de seguridad
- Reportes: ingresos, reservas, gráfico de métodos de pago, exportar CSV
- Google Drive: configurar credenciales, probar conexión, sincronizar
- Configuración: datos del negocio, tarifas, datos de pago, gestión de PINs

#### Base de Datos SQLite
- 10 tablas: clientes, facturas, factura_items, cubiculos, tarifas, reservas, pagos, operadores, configuracion_pagos, sync_log
- Datos de demostración: 12 cubículos, 3 tarifas, 8 reservas, 2 operadores
- Compatible con `facturacion.py` (tablas compartidas)

#### Integración con facturacion.py
- BD compartida `terminal_descanso.db`
- Generación automática de factura al confirmar pago
- Numeración secuencial FACT-YYYY-NNNN

#### Google Drive — archivo `jjgt_pagos`
- 8 hojas: Reservas, Pagos, Clientes, Cubiculos_Estado, Facturas, Dashboard_Diario, Tarifas_Config, Log_Operaciones
- Sincronización automática en tiempo real (con fallback offline)
- Cola de sync pendiente para reconexión posterior
- Sincronización completa manual desde el panel operador

#### Generación de Documentos
- Ticket PDF térmico 80mm con ReportLab (código PIN, WiFi, QR, IVA desglosado)
- Voucher HTML descargable como fallback
- Enlace de WhatsApp con resumen del voucher

#### Diseño y UX
- Modo kiosco táctil con botones ≥72px de altura
- Tema oscuro "Noche de viaje" (#050b1a → #0d1f3c)
- Tipografías Syne + Inconsolata (Google Fonts)
- Animación de estrellas CSS en pantalla de bienvenida
- Grid visual de cubículos con estados codificados por color (verde/rojo/amarillo/violeta)
- Stepper de progreso en todas las pantallas del flujo
- Reloj digital en tiempo real (zona horaria Colombia)
- QR con borde animado pulsante cyan

#### Seguridad
- PINs hasheados con SHA-256
- Máximo 3 intentos fallidos en login de operador
- Datos bancarios solo almacenados en `configuracion_pagos`, no en código
- `credentials.json` externo al código fuente

---

## [Próximamente] — Versiones Futuras

### Planificado para v1.1.0
- [ ] Webhook real de Nequi Business (confirmación automática sin intervención)
- [ ] Webhook real de Daviplata (confirmación automática)
- [ ] Sistema de alertas por WhatsApp al operador (Twilio o WhatsApp Business API)
- [ ] Notificación automática al cliente 30/15/5 minutos antes del vencimiento
- [ ] Extensión de tiempo desde la pantalla del kiosco

### Planificado para v1.2.0
- [ ] Módulo de reservas anticipadas con calendario
- [ ] Código de descuento / cupones promocionales
- [ ] Programa de fidelidad (acumular puntos por horas)
- [ ] App móvil complementaria para el operador (PWA)

### Planificado para v2.0.0
- [ ] Integración con cerradura inteligente (acceso automático con el PIN)
- [ ] Dashboard en tiempo real para el dueño (acceso remoto vía web)
- [ ] Sistema de cámaras (RTSP) integrado en el panel operador
- [ ] Múltiples sucursales (terminales)
- [ ] Multimoneda para turistas extranjeros (USD/EUR)
- [ ] Integración DIAN para facturación electrónica oficial

---

*JJGT · Módulo de Pagos — CHANGELOG*
