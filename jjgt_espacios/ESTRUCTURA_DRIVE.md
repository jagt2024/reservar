# ☁️ ESTRUCTURA GOOGLE DRIVE — archivo `jjgt_pagos`
## JJGT · Módulo de Pagos — Especificación de Hojas

---

## Información General

| Campo | Detalle |
|---|---|
| **Nombre del archivo** | `jjgt_pagos` |
| **Tipo** | Google Sheets |
| **Total de hojas** | 8 |
| **Actualización** | Automática en tiempo real (sync con SQLite) |
| **Acceso** | Service Account (`credentials.json`) |
| **Módulo de configuración** | Panel Operador → ☁️ Google Drive |

---

## HOJA 1 — `Reservas`
> Registro completo de cada reserva realizada

| Col | Campo | Tipo | Ejemplo | Descripción |
|---|---|---|---|---|
| A | ID_Reserva | Número | 42 | ID interno SQLite |
| B | Numero_Reserva | Texto | CR-20250115-0042 | Número único de reserva |
| C | Fecha_Hora | Texto | 2025-01-15 14:35:22 | Fecha y hora de creación |
| D | Cubiculo | Texto | #05 | Número del cubículo |
| E | Cliente_Nombre | Texto | María García | Nombre completo del cliente |
| F | Documento | Texto | 1234567890 | Cédula o pasaporte |
| G | Telefono | Texto | 3105550042 | Celular del cliente |
| H | Email | Texto | maria@email.com | Email (opcional) |
| I | Horas | Número | 2.0 | Tiempo contratado en horas |
| J | Hora_Inicio | Texto | 14:35 | Hora de inicio del servicio |
| K | Hora_Fin_Prog | Texto | 16:35 | Hora de finalización programada |
| L | Hora_Fin_Real | Texto | 16:40 | Hora real de finalización |
| M | Precio_Hora | Número | 15000 | Precio por hora en COP |
| N | Subtotal | Número | 25210.08 | Subtotal antes de IVA |
| O | IVA | Número | 4789.92 | IVA 19% en COP |
| P | Total_COP | Número | 30000 | Total pagado en COP |
| Q | Metodo_Pago | Texto | Nequi | Método de pago usado |
| R | Estado_Pago | Texto | confirmado | pendiente/confirmado/rechazado |
| S | Codigo_Acceso | Texto | 7842 | PIN de acceso al cubículo |
| T | WiFi_SSID | Texto | JJGT-Cubiculo-05 | Red WiFi asignada |
| U | WiFi_Pass | Texto | Desc052025 | Clave WiFi del cubículo |
| V | Num_Factura | Texto | FACT-2025-0087 | Número de factura emitida |
| W | Referencia | Texto | CR-20250115-05 | Referencia externa de pago |
| X | Operador | Texto | sistema | Quién procesó el pago |
| Y | Notas | Texto | - | Notas adicionales |

---

## HOJA 2 — `Pagos`
> Registro de cada transacción de pago

| Col | Campo | Tipo | Ejemplo | Descripción |
|---|---|---|---|---|
| A | ID_Pago | Número | 87 | ID interno SQLite |
| B | ID_Reserva | Número | 42 | FK a tabla reservas |
| C | Num_Reserva | Texto | CR-20250115-0042 | Número de reserva asociada |
| D | Fecha_Pago | Texto | 2025-01-15 14:38:05 | Fecha y hora del pago |
| E | Monto_COP | Número | 30000 | Monto pagado en COP |
| F | Metodo | Texto | Nequi | Plataforma de pago |
| G | Referencia_Externa | Texto | NEQ-2025011542 | Referencia de la plataforma |
| H | Estado | Texto | confirmado | pendiente/confirmado/rechazado/reembolsado |
| I | Confirmado_Por | Texto | sistema | sistema/operador/admin |
| J | Tiempo_Proc_Min | Número | 3 | Minutos desde inicio hasta confirmación |
| K | Notas | Texto | - | Notas del pago |

---

## HOJA 3 — `Clientes`
> Base de datos de viajeros con historial acumulado

| Col | Campo | Tipo | Ejemplo | Descripción |
|---|---|---|---|---|
| A | ID_Cliente | Número | 18 | ID interno SQLite |
| B | Nombre | Texto | María García López | Nombre completo |
| C | Tipo_Doc | Texto | CC | CC/Pasaporte/CE/NIT |
| D | Num_Doc | Texto | 1234567890 | Número de documento |
| E | Telefono | Texto | 3105550042 | Celular |
| F | Email | Texto | maria@email.com | Email |
| G | Ciudad | Texto | Bogotá | Ciudad de origen |
| H | Req_Factura_Empresa | Texto | No | Sí/No |
| I | Razon_Social | Texto | - | Razón social si aplica |
| J | NIT_Empresa | Texto | - | NIT de la empresa |
| K | Total_Reservas | Número | 3 | Número de visitas acumuladas |
| L | Total_Gastado_COP | Número | 90000 | Total histórico gastado |
| M | Primera_Visita | Texto | 2025-01-10 | Fecha de primera reserva |
| N | Ultima_Visita | Texto | 2025-01-15 | Fecha de última reserva |
| O | Notas | Texto | - | Notas del cliente |

---

## HOJA 4 — `Cubiculos_Estado`
> Estado en **tiempo real** de cada cubículo (actualización automática)

| Col | Campo | Tipo | Ejemplo | Descripción |
|---|---|---|---|---|
| A | Cubiculo_ID | Número | 5 | ID interno |
| B | Numero | Texto | #05 | Número del cubículo |
| C | Estado | Texto | ocupado | libre/ocupado/por_liberar/mantenimiento |
| D | Cliente_Actual | Texto | María García | Nombre del cliente actual (si ocupado) |
| E | Hora_Inicio | Texto | 14:35 | Inicio de reserva activa |
| F | Hora_Fin_Prog | Texto | 16:35 | Fin programado de reserva activa |
| G | Tiempo_Rest_Min | Número | 78 | Minutos restantes (si ocupado) |
| H | WiFi_SSID | Texto | JJGT-Cubiculo-05 | Red WiFi del cubículo |
| I | WiFi_Pass | Texto | Desc052025 | Contraseña WiFi actual |
| J | Codigo_Acceso | Texto | 7842 | PIN activo (si hay reserva) |
| K | Total_Reservas | Número | 145 | Reservas históricas en este cubículo |
| L | Ingresos_Total | Número | 2175000 | Ingresos históricos generados |
| M | Ultimo_Mant | Texto | 2025-01-14 | Fecha último mantenimiento |
| N | Notas | Texto | - | Estado o notas actuales |

> 📌 Esta hoja se actualiza automáticamente con cada cambio de estado de cualquier cubículo.

---

## HOJA 5 — `Facturas`
> Espejo completo de todas las facturas emitidas (para contabilidad)

| Col | Campo | Tipo | Ejemplo | Descripción |
|---|---|---|---|---|
| A | Num_Factura | Texto | FACT-2025-0087 | Número único de factura |
| B | Fecha_Emision | Texto | 2025-01-15 | Fecha de emisión |
| C | Fecha_Venc | Texto | 2025-01-15 | Fecha de vencimiento |
| D | Cliente | Texto | María García | Nombre del cliente |
| E | Documento | Texto | 1234567890 | Documento del cliente |
| F | Email | Texto | maria@email.com | Email del cliente |
| G | Razon_Social | Texto | - | Razón social si es empresa |
| H | NIT_Emp | Texto | - | NIT de la empresa |
| I | Descripcion | Texto | Cubículo #05 · 2h · WiFi+Baño+Carga | Descripción del servicio |
| J | Cantidad_Horas | Número | 2.0 | Horas facturadas |
| K | Precio_Hora | Número | 15000 | Precio unitario por hora |
| L | Subtotal | Número | 25210.08 | Subtotal antes de IVA |
| M | Descuento | Número | 0 | Descuento aplicado en COP |
| N | Base_Gravable | Número | 25210.08 | Base para cálculo de IVA |
| O | IVA_19pct | Número | 4789.92 | Valor del IVA |
| P | Total_COP | Número | 30000 | Total de la factura |
| Q | Metodo_Pago | Texto | Nequi | Método de pago |
| R | Estado | Texto | pagada | emitida/pagada/anulada |
| S | Num_Reserva | Texto | CR-20250115-0042 | Reserva asociada |
| T | Cubiculo | Texto | #05 | Cubículo del servicio |
| U | Creado_En | Texto | 2025-01-15 14:38:10 | Timestamp de creación |

---

## HOJA 6 — `Dashboard_Diario`
> Resumen automático por día — **ideal para KPIs del negocio**

| Col | Campo | Tipo | Ejemplo | Descripción |
|---|---|---|---|---|
| A | Fecha | Texto | 2025-01-15 | Fecha del resumen |
| B | Total_Reservas | Número | 28 | Total de reservas iniciadas |
| C | Completadas | Número | 25 | Reservas con pago confirmado |
| D | Canceladas | Número | 3 | Reservas canceladas o rechazadas |
| E | Ingresos_Brutos | Número | 375000 | Suma de totales pagados (con IVA) |
| F | IVA_Recaudado | Número | 59874 | Total IVA del día |
| G | Ingresos_Netos | Número | 315126 | Ingresos sin IVA |
| H | Nequi_COP | Número | 180000 | Ingresos por Nequi |
| I | Daviplata_COP | Número | 90000 | Ingresos por Daviplata |
| J | Efectivo_COP | Número | 60000 | Ingresos en efectivo |
| K | PSE_COP | Número | 30000 | Ingresos por PSE |
| L | MP_COP | Número | 15000 | Ingresos por MercadoPago |
| M | Otros_COP | Número | 0 | Otros métodos |
| N | Ocupacion_Pct | Número | 72.5 | % promedio de ocupación del día |
| O | Hora_Pico | Texto | 14:00-15:00 | Hora con más reservas |
| P | Tiempo_Prom_Min | Número | 95 | Duración promedio de reserva |
| Q | Clientes_Nuevos | Número | 18 | Clientes que visitan por primera vez |
| R | Clientes_Recur | Número | 7 | Clientes recurrentes |
| S | Fact_Min | Número | 10000 | Factura más baja del día |
| T | Fact_Max | Número | 42000 | Factura más alta del día |
| U | Ticket_Prom_COP | Número | 15000 | Promedio por reserva |

---

## HOJA 7 — `Tarifas_Config`
> Registro de tarifas configuradas (auditoría de cambios de precio)

| Col | Campo | Tipo | Ejemplo | Descripción |
|---|---|---|---|---|
| A | ID | Número | 1 | ID de la tarifa |
| B | Nombre | Texto | Estándar | Nombre de la tarifa |
| C | Descripcion | Texto | Tarifa normal diurna | Descripción |
| D | Precio_Hora_COP | Número | 15000 | Precio por hora en COP |
| E | Hora_Ini_Espec | Texto | - | Inicio de horario especial |
| F | Hora_Fin_Espec | Texto | - | Fin de horario especial |
| G | Desc_3h_Pct | Número | 10 | Descuento para 3+ horas (%) |
| H | Desc_6h_Pct | Número | 20 | Descuento para 6+ horas (%) |
| I | Activo | Texto | Sí | Si está activa actualmente |
| J | Vigente_Desde | Texto | 2025-01-01 | Fecha de vigencia |
| K | Notas | Texto | - | Notas adicionales |

### Tarifas de ejemplo precargadas:
| Tarifa | Precio/hora | Horario | Desc 3h | Desc 6h |
|---|---|---|---|---|
| Estándar | $15.000 COP | 06:00–23:59 | 10% | 20% |
| Madrugada | $10.000 COP | 00:00–05:59 | 10% | 20% |
| Festivo | $18.000 COP | Días festivos | 10% | 20% |

---

## HOJA 8 — `Log_Operaciones`
> Auditoría completa de todas las acciones del sistema

| Col | Campo | Tipo | Ejemplo | Descripción |
|---|---|---|---|---|
| A | Timestamp | Texto | 2025-01-15 14:38:05 | Fecha y hora exacta (TZ Colombia) |
| B | Tipo_Op | Texto | nueva_reserva | Tipo de operación (ver lista abajo) |
| C | Reserva_ID | Número | 42 | ID de reserva relacionada (si aplica) |
| D | Cubiculo | Texto | #05 | Cubículo relacionado (si aplica) |
| E | Operador | Texto | sistema | Quién ejecutó la operación |
| F | Descripcion | Texto | Reserva CR-0042 creada | Descripción detallada |
| G | Valor_Ant | Texto | libre | Valor anterior (si aplica) |
| H | Valor_Nuevo | Texto | ocupado | Valor nuevo (si aplica) |
| I | IP | Texto | 192.168.1.10 | IP del dispositivo |
| J | Estado | Texto | exito | exito/fallo |
| K | Notas | Texto | {"total":30000} | Datos adicionales en JSON |

### Tipos de operación registrados:
| Tipo | Cuándo |
|---|---|
| `nueva_reserva` | Al crear una reserva y confirmar el pago |
| `pago_confirmado` | Al marcar un pago como confirmado |
| `pago_rechazado` | Al rechazar un pago pendiente |
| `cubiculo_liberado` | Al liberar un cubículo anticipadamente |
| `extension_tiempo` | Al extender el tiempo de una reserva |
| `mantenimiento_inicio` | Al poner un cubículo en mantenimiento |
| `mantenimiento_fin` | Al marcar el mantenimiento como completado |
| `configuracion_cambio` | Al modificar configuración del sistema |
| `sync_completa` | Al ejecutar sincronización total Drive |
| `pin_cambiado` | Al cambiar el PIN de un operador |
| `error` | Cuando ocurre un error en el sistema |

---

## Sincronización y Estado de Conexión

```
Estado de Drive en Panel Operador:
  🟢 Drive conectado    → credentials.json válido, sync funcionando
  🟡 Sync pendiente     → Registros en cola esperando conexión
  🔴 Sin conexión Drive → Sin credentials.json o sin internet
```

### Comportamiento ante desconexión
1. Si Drive no está disponible, la operación continúa solo en SQLite
2. Se marca en tabla `sync_log` con `sync_pendiente = 1`
3. Al reconectar (o manual desde el panel), se ejecuta `sincronizacion_completa()`
4. Todos los registros pendientes se suben a Drive

---

*JJGT · Estructura Google Drive `jjgt_pagos` v1.0.0*
