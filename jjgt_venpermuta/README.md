# 🚗 JJGT — Plataforma de Vehículos Colombia
### Aplicación Streamlit · v2.0

---

## 📦 Instalación y ejecución

### Requisitos previos
- Python 3.9+
- pip

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Ejecutar la aplicación
```bash
streamlit run app.py
```

### 3. Abrir en el navegador
La app se abrirá automáticamente en `http://localhost:8501`

---

## 🗂️ Estructura del proyecto

```
jjgt_streamlit/
├── app.py              ← Aplicación principal (router + páginas)
├── data.py             ← Datos: vehículos, historial, notificaciones
├── components.py       ← Componentes HTML reutilizables
├── styles.py           ← CSS global de la aplicación
├── requirements.txt    ← Dependencias Python
├── .streamlit/
│   └── config.toml     ← Configuración de tema Streamlit
└── README.md
```

---

## 🚀 Funcionalidades implementadas

### 🏠 Inicio
- Banner de bienvenida / saludo personalizado según hora
- Estadísticas de la plataforma (15K+ vehículos, 8K+ usuarios)
- Acciones rápidas (8 botones)
- Vehículos destacados (grid 3 columnas)
- Permutas activas

### 🔍 Explorar
- Búsqueda en tiempo real por nombre, modelo, ciudad
- Filtros avanzados: categoría, tipo anuncio, ciudad, rango de precio
- Grid de resultados con tarjetas completas
- Acceso al detalle de cada vehículo

### 🚗 Detalle de vehículo
- Galería de fotos con thumbnails (publicaciones propias)
- Reproducción de video
- Especificaciones completas
- Tarjeta del vendedor con datos de contacto
- Botones: WhatsApp, Llamar, Proponer permuta
- Reseñas del vendedor
- Gestión del aviso (editar/eliminar para publicaciones propias)

### ➕ Publicar
- Carga de hasta 10 fotos (JPG, PNG, WEBP)
- Carga de video (MP4, MOV)
- Vista previa de fotos con portada identificada
- Formulario completo: marca, modelo, año, km, combustible, transmisión
- Datos del vendedor auto-completados con la sesión
- Validación de campos obligatorios
- Publicación aparece en "Mis Avisos" y "Explorar"

### 📋 Mis Avisos (Historial)
- Filtros: Todos / Activos / Pendientes / Cerrados
- Estado visual por colores (verde/amarillo/azul/rojo)
- Botones: Ver aviso, Editar, Eliminar (solo activos/pendientes)
- Eliminación con confirmación

### 🔔 Notificaciones
- Grupos por tiempo (Hoy, Ayer, Esta semana)
- Badge de no leídas
- Marcar todas como leídas

### 💬 Soporte / Chat
- Chatbot con respuestas automáticas
- Respuestas rápidas predefinidas
- Input libre de mensajes
- FAQ con acordeón

### 👤 Perfil
- Header con avatar, nombre, estadísticas
- Tarjeta de lealtad con barra de progreso
- Subpáginas: Mis datos, Mis ciudades, Notificaciones, Privacidad, Ayuda

### 🔐 Autenticación
- Login con email/contraseña
- Registro con validación completa
- Recuperar contraseña
- Cerrar sesión

### 🔄 Permutas
- Vista de vehículos disponibles para permuta
- Proponer permuta (requiere sesión)

---

## 🔑 Acceso de prueba

Para probar la aplicación puedes usar cualquier email/contraseña:
- **Email:** `josegarjagt@gmail.com` (cuenta administrador JJGT)
- **Contraseña:** cualquier texto

---

## 🎨 Diseño

- **Colores:** Rojo JJGT `#C41E3A` + Navy `#1A1A2E` + Oro `#F5A623`
- **Tipografía:** Bebas Neue (títulos) + DM Sans (cuerpo)
- **Tema:** Claro con soporte de modo oscuro
- **Colombia 🇨🇴:** Precios en COP, ciudades colombianas

---

## 📱 Equivalencia con la PWA original

| PWA (HTML) | Streamlit |
|------------|-----------|
| Pantalla Inicio | `page_home()` |
| Explorar + filtros | `page_explore()` |
| Detalle vehículo | `page_vehicle_detail()` |
| Publicar con foto/video | `page_publish()` |
| Mis avisos + eliminar | `page_history()` |
| Notificaciones | `page_notifications()` |
| Chat soporte | `page_support()` |
| Mi perfil | `page_profile()` |
| Mis datos | `page_profile_mydata()` |
| Mis ciudades | `page_profile_cities()` |
| Config notificaciones | `page_profile_notifconfig()` |
| Privacidad | `page_profile_privacy()` |
| Ayuda/FAQ | `page_profile_help()` |
| Login / Registro | `page_login()` / `page_register()` |
| Permutas | `page_permutas()` |

---

Hecho con ❤️ para Colombia 🇨🇴 · JJGT Vehículos 2024

---

## v2.1 — Cambios

### Bugs corregidos
1. **DuplicateWidgetID** — Todas las keys de botones ahora incluyen índice + ID de vehículo, garantizando unicidad global.
2. **HTML visible en tarjetas** — Las tarjetas de vehículos destacados ahora usan `st.container()` nativo en lugar de HTML crudo.
3. **Carga de datos desde Google Sheets** — Integración completa con el archivo `jjgt_gestion`.

### Google Sheets — Configuración

Crea `.streamlit/secrets.toml` con esta estructura:
```toml
[sheetsemp]
credentials_sheet = '''
{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
  "client_email": "...",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
'''
```

### Hojas leídas de `jjgt_gestion`
| Hoja | Datos |
|------|-------|
| `🚗 VEHÍCULOS` | 15 vehículos con specs completas |
| `👥 USUARIOS` | 10 usuarios registrados |
| `🔄 PERMUTAS` | 8 propuestas de permuta |
| `📋 PUBLICACIONES` | 15 publicaciones activas |
| `📦 HISTORIAL` | 8 registros de transacciones |
| `🔔 NOTIFICACIONES` | 12 notificaciones |

Sin conexión a Sheets, la app usa los **datos estáticos locales** automáticamente.
