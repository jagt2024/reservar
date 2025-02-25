# Workflow de Atención
## Sistema de Gestión de Citas para Clínica Psicológica

### 1. Diagrama General del Proceso
```
[Solicitud de Cita] → [Verificación de Disponibilidad] → [Programación] → [Confirmación] → 
[Recordatorio] → [Atención] → [Registro de Asistencia] → [Seguimiento] → [Cierre]
```

### 2. Flujos Detallados por Etapa

#### 2.1 Solicitud de Cita

**Canales de Solicitud:**
- Portal web
- Aplicación móvil
- Vía telefónica
- Presencial

**Proceso:**
1. **Identificación del Paciente**
   - Para pacientes nuevos:
     - Registro de datos personales
     - Asignación de ID único
     - Verificación de contacto
   - Para pacientes existentes:
     - Búsqueda por ID/documento
     - Verificación de datos
     - Actualización si es necesario

2. **Selección de Servicio**
   - Presentación del catálogo de servicios
   - Filtrado por categoría (Psicología, Trabajo Social, etc.)
   - Información detallada del servicio
   - Verificación de requisitos previos

3. **Captura de Motivo**
   - Registro del motivo de consulta
   - Nivel de urgencia
   - Necesidades especiales
   - Preferencias de atención

#### 2.2 Verificación de Disponibilidad

1. **Consulta de Agenda**
   - Verificación automática de horarios
   - Filtrado por servicio
   - Filtrado por profesional (si es solicitado)
   - Verificación de cupos disponibles

2. **Propuesta de Opciones**
   - Presentación de fechas disponibles
   - Opciones de horarios
   - Alternativas de profesionales
   - Sugerencias de fechas cercanas

#### 2.3 Programación

1. **Reserva del Espacio**
   - Bloqueo temporal del horario (5 minutos)
   - Asignación de profesional
   - Registro de duración esperada
   - Asignación de sala/consultorio

2. **Registro de Información Adicional**
   - Datos complementarios del servicio
   - Documentación requerida
   - Instrucciones especiales
   - Forma de pago (si aplica)

#### 2.4 Confirmación

1. **Generación de Confirmación**
   - Creación de código de cita
   - Detalle del servicio reservado
   - Información del profesional asignado
   - Fecha, hora y lugar

2. **Envío de Notificaciones**
   - Al paciente:
     - Correo electrónico con detalles
     - Mensaje WhatsApp con confirmación
     - Opción de agregar a calendario
   - Al profesional:
     - Actualización de agenda
     - Notificación de nueva cita
     - Resumen del caso
   - A la clínica:
     - Actualización de agenda general
     - Registro en sistema

#### 2.5 Gestión Pre-Cita

1. **Recordatorios Automáticos**
   - 48 horas antes: Primer recordatorio
   - 24 horas antes: Segundo recordatorio
   - 2 horas antes: Recordatorio final
   - Confirmación de asistencia requerida

2. **Cambios y Cancelaciones**
   - Solicitud de modificación:
     - Verificación de disponibilidad
     - Registro del cambio
     - Notificaciones actualizadas
   - Solicitud de cancelación:
     - Registro de motivo
     - Liberación del espacio
     - Notificación a todas las partes
     - Propuesta de reprogramación

#### 2.6 Atención

1. **Check-in**
   - Registro de llegada
   - Verificación de puntualidad
   - Notificación al profesional
   - Instrucciones de espera

2. **Preparación de Sesión**
   - Acceso al expediente
   - Revisión de historial
   - Preparación de materiales
   - Acondicionamiento del espacio

3. **Desarrollo de la Sesión**
   - Control de tiempo
   - Registro de inicio/fin
   - Notificación de extensión (si aplica)
   - Bloqueo de interrupciones

#### 2.7 Registro Post-Atención

1. **Registro Profesional**
   - Notas de sesión
   - Evolución del caso
   - Recomendaciones
   - Próximos pasos

2. **Gestión Administrativa**
   - Registro de asistencia
   - Actualización de expediente
   - Generación de factura/recibo
   - Programación de seguimiento

#### 2.8 Seguimiento

1. **Programación de Siguiente Cita**
   - Recomendación automática
   - Verificación de disponibilidad
   - Reserva anticipada
   - Confirmación inmediata

2. **Encuesta de Satisfacción**
   - Envío automático post-atención
   - Calificación de servicio
   - Comentarios y sugerencias
   - Detección de PQRS

3. **Alertas de Continuidad**
   - Recordatorio de tratamiento
   - Alerta de seguimiento pendiente
   - Notificación de resultados (si aplica)
   - Información complementaria

#### 2.9 Cierre del Ciclo

1. **Actualización de Estadísticas**
   - Registro en métricas
   - Actualización de dashboard
   - Historial de atenciones
   - Indicadores de rendimiento

2. **Análisis de Datos**
   - Puntualidad
   - Satisfacción
   - Efectividad
   - Optimización de recursos

### 3. Flujos Especiales

#### 3.1 Gestión de Urgencias

1. **Detección de Urgencia**
   - Palabras clave en solicitud
   - Marcado manual de prioridad
   - Categorización de nivel

2. **Protocolo de Atención Urgente**
   - Notificación inmediata a profesionales
   - Liberación de espacios (si es necesario)
   - Comunicación directa
   - Seguimiento especial

#### 3.2 Gestión de Grupos

1. **Configuración de Sesión Grupal**
   - Definición de capacidad
   - Asignación de espacio
   - Requisitos específicos
   - Material necesario

2. **Gestión de Participantes**
   - Control de cupo
   - Lista de asistentes
   - Confirmaciones individuales
   - Manejo de lista de espera

#### 3.3 Manejo de PQRS

1. **Captura de Incidencias**
   - Formulario específico
   - Categorización del caso
   - Nivel de prioridad
   - Asignación de responsable

2. **Flujo de Resolución**
   - Notificación automática
   - Tiempos de respuesta definidos
   - Seguimiento de estado
   - Comunicación con el paciente
   - Cierre y valoración

### 4. Reglas de Negocio Aplicadas

1. **Políticas de Cancelación**
   - Tiempo mínimo de aviso: 24 horas
   - Penalizaciones por cancelaciones tardías
   - Límite de cancelaciones consecutivas
   - Excepciones por causa mayor

2. **Reglas de Asignación**
   - Balanceo de carga entre profesionales
   - Continuidad con mismo profesional
   - Especialización por tipo de servicio
   - Preferencias registradas del paciente

3. **Política de Recordatorios**
   - Frecuencia progresiva
   - Confirmación obligatoria
   - Escalamiento por no respuesta
   - Canales alternativos

4. **Gestión de Tiempo**
   - Intervalos entre citas: 15 minutos
   - Buffer para servicios complejos
   - Tiempo máximo de espera: 15 minutos
   - Registro de puntualidad

### 5. Integraciones del Workflow

1. **Sistema de Pagos**
   - Verificación de estado de cuenta
   - Registro de transacciones
   - Facturación automática
   - Recordatorios de pago

2. **Expediente Clínico**
   - Acceso a historial
   - Actualización automática
   - Vinculación de notas
   - Seguimiento de evolución

3. **Business Intelligence**
   - Métricas de rendimiento
   - Análisis de satisfacción
   - Optimización de agenda
   - Predicción de demanda
