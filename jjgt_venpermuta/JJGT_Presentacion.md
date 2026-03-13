# 🚗 JJGT Vehículos Colombia
## Plataforma Digital de Compra, Venta y Permuta de Vehículos

**Documento de Presentación · 2025**  
📧 josegarjagt@gmail.com · 🇨🇴 Colombia

---

## 1. ¿Qué es JJGT Vehículos?

JJGT Vehículos es una plataforma web colombiana diseñada para conectar compradores y vendedores de vehículos de forma rápida, segura y transparente. Permite publicar, explorar y gestionar avisos de venta y permuta de vehículos desde cualquier dispositivo, sin necesidad de intermediarios.

La plataforma está construida sobre tecnología moderna (Streamlit + Google Sheets + Google Drive), lo que permite un despliegue en la nube de bajo costo, mantenimiento simplificado y acceso inmediato desde el navegador sin instalaciones adicionales.

| Métrica | Valor |
|---------|-------|
| Ciudades activas | 3+ (Bogotá, Medellín, Cali) |
| Acceso | 100% Web — sin instalación |
| Tipos de aviso | Venta · Permuta · Ambos |
| Almacenamiento de medios | Google Drive |
| Hosting | Streamlit Cloud |

### Misión

Democratizar el acceso al mercado de vehículos usados en Colombia, ofreciendo una herramienta digital accesible, confiable y fácil de usar para vendedores particulares y compradores en todo el territorio nacional.

### Visión

Ser la plataforma de referencia para la compra, venta y permuta de vehículos en Colombia, reconocida por su transparencia, su tecnología y la confianza que genera en cada transacción.

---

## 2. Funcionalidades Principales

### Para los Usuarios

| Módulo | Descripción |
|--------|-------------|
| 🔍 Explorar catálogo | Búsqueda y filtrado por ciudad, precio, tipo y características del vehículo. |
| 📝 Publicar avisos | Formulario completo con fotos, video, precio, descripción y datos de contacto. |
| 🔄 Permuta de vehículos | Proponer intercambios con o sin diferencia de precio entre vehículos. |
| 📦 Mis Avisos | Gestión del historial de publicaciones: ver, editar y eliminar avisos propios. |
| 🔔 Notificaciones | Alertas sobre visitas, mensajes y propuestas recibidas. |
| ⭐ Reseñas | Sistema de valoración entre usuarios para generar confianza en la plataforma. |
| 💬 Soporte | Chat de soporte integrado para resolver dudas y reportar problemas. |
| 🔑 Seguridad | Contraseñas con hash SHA-256, recuperación por correo y cambio de cuenta. |

### Para el Administrador

| Módulo | Descripción |
|--------|-------------|
| 👥 Gestión de usuarios | Listar, cambiar rol, cambiar contraseña y eliminar cuentas registradas. |
| 📊 Dashboard | Métricas automáticas: vehículos activos, publicaciones, usuarios, visitas. |
| 🔐 Panel de acceso | Configuración de cuenta administrador y control de acceso. |
| 📧 Notificaciones automáticas | Correo HTML al admin en cada nueva publicación con foto y datos del vehículo. |

---

## 3. Arquitectura Tecnológica

| Componente | Tecnología | Descripción |
|------------|-----------|-------------|
| Frontend / App | Streamlit (Python) | Framework web interactivo, 100% en Python, sin HTML/JS manual. |
| Base de datos | Google Sheets | Hojas de cálculo en la nube como backend estructurado (7 hojas). |
| Almacenamiento de medios | Google Drive | Fotos y videos de vehículos con fallback a base64 en Sheets. |
| Autenticación | SHA-256 + Sheets | Contraseñas hasheadas almacenadas en columna segura. |
| Correo electrónico | SMTP Gmail SSL | Notificaciones automáticas a admin y usuarios (port 465). |
| Exportación | Excel (openpyxl) | Backup y exportación de datos en formato .xlsx. |
| Hosting | Streamlit Cloud | Despliegue gratuito, accesible desde cualquier navegador. |

### Estructura de Datos — Google Sheets

La información se organiza en 7 hojas principales dentro del archivo `jjgt_gestion`:

- 🚗 **VEHÍCULOS** — catálogo completo y publicaciones de usuarios
- 📋 **PUBLICACIONES** — registro de avisos activos con métricas
- 👥 **USUARIOS** — cuentas, roles y hash de contraseñas
- 📦 **HISTORIAL** — registro de transacciones por usuario
- 🔄 **PERMUTAS** — propuestas de intercambio
- 🔔 **NOTIFICACIONES** — alertas del sistema
- ⭐ **RESEÑAS** — valoraciones entre usuarios

---

## 4. Flujo de Usuario

### Vendedor — Publicar un vehículo

1. Crear cuenta o ingresar con correo y contraseña.
2. Completar el formulario de publicación: fotos, video, precio, descripción, ciudad y datos de contacto.
3. El sistema sube los medios a Google Drive automáticamente.
4. La publicación queda activa en el catálogo y se registra en Google Sheets.
5. El administrador recibe un correo de notificación con los detalles del vehículo.
6. El vendedor gestiona sus avisos desde "Mis Avisos": ver, editar o eliminar.

### Comprador — Explorar y contactar

1. Explorar el catálogo con filtros por ciudad, rango de precio, tipo y características.
2. Ver el detalle completo del vehículo: galería de fotos, video, ficha técnica y datos del vendedor.
3. Contactar al vendedor directamente por WhatsApp o proponer una permuta.
4. Valorar la experiencia con el sistema de reseñas.

### Permuta — Intercambio de vehículos

1. Desde el detalle del vehículo, el interesado selecciona uno de sus propios vehículos.
2. Propone el intercambio con o sin diferencia de precio.
3. El vendedor recibe la propuesta por correo y en la plataforma.
4. Ambas partes pueden aceptar, rechazar o negociar la propuesta.

---

## 5. Seguridad y Privacidad

| Característica | Descripción |
|----------------|-------------|
| 🔒 Hash de contraseñas | SHA-256 aplicado sobre cada contraseña antes de guardarla. Nunca se almacena texto plano. |
| 📧 Recuperación segura | Contraseña temporal generada aleatoriamente y enviada al correo registrado. |
| 🔑 Cambio de cuenta | Limpieza completa de la sesión activa al cambiar de usuario, sin datos residuales. |
| 👤 Control de roles | Tres niveles: Usuario, Vendedor y Administrador. Solo el admin accede al panel. |
| 🛡️ Credenciales seguras | Las credenciales de Google se almacenan en `secrets.toml`, nunca en el código. |
| 🗑️ Eliminación real | Al eliminar una publicación se borra la fila en Sheets — no es una marca lógica. |

---

## 6. Contacto

¿Quieres saber más sobre JJGT Vehículos?

📧 **josegarjagt@gmail.com**  
🇨🇴 Colombia · 2025

---

*JJGT Vehículos Colombia · Plataforma Digital · 2025*
