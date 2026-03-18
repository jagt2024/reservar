# 🖥️ JAGT Hosting Panel — Documentación Completa

> **Dominio:** josegart  
> **Admin:** josegarjagt@gmail.com  
> **Repositorio:** github.com/jagt2024/Reservar/  
> **Plataforma:** Streamlit Cloud (disponible 24/7)

---

## 📋 Tabla de Contenidos

1. [Arquitectura del Sistema](#arquitectura)
2. [Estructura de Archivos](#estructura)
3. [Paso a Paso: Implementación](#implementacion)
4. [Configuración de Secrets](#secrets)
5. [Google Drive Integration](#drive)
6. [Backups Automáticos](#backups)
7. [Seguridad & Anti-Spam](#seguridad)
8. [Disponibilidad 24/7](#disponibilidad)
9. [Gestión de Aplicaciones](#apps)
10. [Migración (cuando decidas)](#migracion)

---

## 1. Arquitectura del Sistema {#arquitectura}

```
┌─────────────────────────────────────────────────────────┐
│                   JAGT HOSTING SYSTEM                   │
│                    josegart.io                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────┐   ┌──────────────────────┐    │
│  │  Panel de Control   │   │  Apps Gestionadas    │    │
│  │  (app.py)           │   │                      │    │
│  │  Streamlit Cloud    │   │  • jagt_landing.py   │    │
│  │  🔐 Auth + RBAC     │   │  • reservar/         │    │
│  │  📊 Dashboard       │   │  • otras apps...     │    │
│  │  💾 Backups         │   │                      │    │
│  │  🛡️ Anti-Spam       │   │  → jagt2024/Reservar/│    │
│  └─────────┬───────────┘   └──────────┬───────────┘    │
│            │                          │                 │
│            ▼                          ▼                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │              GitHub (jagt2024/Reservar)          │   │
│  │  • Código fuente de todas las apps               │   │
│  │  • GitHub Actions → Backup diario 1AM Colombia   │   │
│  └─────────────────────┬───────────────────────────┘   │
│                         │                               │
│            ┌────────────┴────────────┐                  │
│            ▼                         ▼                  │
│  ┌──────────────────┐  ┌─────────────────────────────┐ │
│  │  SQLite Local    │  │  Google Drive               │ │
│  │  hosting_jagt.db │  │  📊 hosting-jagt.xlsx       │ │
│  │  • apps          │  │  • Apps registradas         │ │
│  │  • backups       │  │  • Historial backups        │ │
│  │  • spam_rules    │  │  • Reglas spam              │ │
│  │  • users         │  │  • Usuarios                 │ │
│  │  • access_log    │  │  • Logs de acceso           │ │
│  └──────────────────┘  └─────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Estructura de Archivos {#estructura}

```
jagt2024/Reservar/
│
├── hosting_panel/                  ← Panel de Control JAGT
│   ├── app.py                      ← Aplicación principal
│   ├── requirements.txt            ← Dependencias Python
│   ├── hosting_jagt.db             ← Base de datos SQLite
│   ├── .streamlit/
│   │   └── secrets.toml            ← Credenciales (NO subir a Git)
│   └── scripts/
│       ├── backup_runner.py        ← Script de backup
│       └── middleware_logger.py    ← Logger de seguridad
│
├── .github/
│   └── workflows/
│       └── backup.yml              ← GitHub Action backup diario
│
├── pagina_web/
│   └── jagt_landing.py             ← Landing page personal
│
├── [otras apps]/
│   └── *.py                        ← Tus aplicaciones
│
└── .gitignore                      ← Protege secrets.toml
```

---

## 3. Paso a Paso: Implementación {#implementacion}

### PASO 1 — Descargar archivos generados

Descarga los archivos desde el panel y colócalos en tu repositorio local:

```bash
# Estructura en tu PC
Reservar/
├── hosting_panel/app.py
├── hosting_panel/requirements.txt
├── hosting_panel/scripts/backup_runner.py
└── .github/workflows/backup.yml
```

### PASO 2 — Configurar .gitignore

Agrega estas líneas a tu `.gitignore`:

```gitignore
# Secrets — NUNCA subir a GitHub
.streamlit/secrets.toml
google_credentials.json
*.db
__pycache__/
.env
```

### PASO 3 — Crear secrets.toml local

Crea `.streamlit/secrets.toml` en la carpeta `hosting_panel/`:

```toml
[google]
DRIVE_FOLDER_ID = "tu_folder_id_aqui"
# Para producción: agrega las credenciales de cuenta de servicio

[github]
GITHUB_TOKEN = "ghp_tu_token_personal"
REPO_OWNER = "jagt2024"
REPO_NAME = "Reservar"

[email]
SMTP_USER = "josegarjagt@gmail.com"
SMTP_PASSWORD = "tu_app_password_de_gmail"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

[database]
SQLITE_PATH = "hosting_jagt.db"

[admin]
DEFAULT_USER = "josegart"
DEFAULT_PASS = "jagt2024!"    # Cambia esto en el panel
```

### PASO 4 — Subir a GitHub

```bash
cd /ruta/a/tu/repositorio/Reservar

git add hosting_panel/
git add .github/
git add .gitignore
git commit -m "feat: JAGT Hosting Panel v1.0

- Panel de administración con auth
- Gestión de apps, backups, spam
- GitHub Actions backup diario
- Integración Google Drive (hosting-jagt.xlsx)"

git push origin main
```

### PASO 5 — Desplegar en Streamlit Cloud

1. Abre **https://share.streamlit.io**
2. Inicia sesión con tu cuenta GitHub (jagt2024)
3. Clic en **"New app"**
4. Configura:
   - **Repository:** `jagt2024/Reservar`
   - **Branch:** `main`
   - **Main file path:** `hosting_panel/app.py`
   - **App URL:** `josegart-hosting` → queda como `josegart-hosting.streamlit.app`
5. Clic en **"Deploy!"**
6. Espera ~2 minutos mientras se construye

### PASO 6 — Configurar Secrets en Streamlit Cloud

En tu app desplegada:
1. Clic en el menú **"⋮" → Settings**
2. Sección **"Secrets"**
3. Pega el contenido de tu `secrets.toml`
4. Clic **Save** → la app se reinicia automáticamente

### PASO 7 — Configurar GitHub Actions Secrets

En GitHub → `jagt2024/Reservar` → Settings → Secrets and variables → Actions:

| Secret | Valor |
|--------|-------|
| `GOOGLE_CREDENTIALS_JSON` | JSON de tu cuenta de servicio Google |
| `DRIVE_FOLDER_ID` | ID de la carpeta en Google Drive |

---

## 4. Configuración de Secrets {#secrets}

### Obtener Google Drive Credentials

1. Ve a **console.cloud.google.com**
2. Crea un proyecto nuevo (ej: "jagt-hosting")
3. Activa la API: **Google Drive API**
4. Ve a **Credentials → Create Credentials → Service Account**
5. Nombra: `jagt-hosting-backup`
6. Rol: `Editor`
7. Descarga el JSON de la cuenta de servicio
8. En Google Drive, crea una carpeta llamada **"JAGT-Hosting"**
9. Comparte esa carpeta con el email de la cuenta de servicio (termina en `@*.iam.gserviceaccount.com`)
10. Copia el ID de la carpeta (está en la URL de Drive)

### Obtener GitHub Token

1. GitHub → Settings → Developer settings → Personal access tokens
2. Clic **"Generate new token (classic)"**
3. Permisos necesarios: `repo`, `workflow`
4. Copia el token (empieza con `ghp_`)

---

## 5. Google Drive Integration {#drive}

El archivo **`hosting-jagt.xlsx`** en tu Google Drive contiene:

| Hoja | Contenido |
|------|-----------|
| 📊 Resumen | Info general del hosting, fechas de backup |
| 📦 Aplicaciones | Todas las apps registradas con estado |
| 💾 Backups | Historial completo de backups |
| 🛡️ Spam_Rules | Reglas de seguridad activas |
| 👥 Usuarios | Lista de usuarios del panel |

El archivo se actualiza automáticamente cada día a la 1 AM (hora Colombia).

---

## 6. Backups Automáticos {#backups}

### Flujo del Backup Diario

```
1:00 AM Colombia
    ↓
GitHub Actions se activa (en la nube, sin tu PC)
    ↓
Ejecuta backup_runner.py
    ↓
Lee datos de hosting_jagt.db
    ↓
Genera hosting-jagt.xlsx
    ↓
Sube/actualiza en Google Drive → carpeta "JAGT-Hosting"
    ↓
Registra el backup en SQLite
    ↓
✅ Backup completado (tu PC puede estar apagada)
```

### Backup Manual (desde el panel)

1. Ve a **Aplicaciones** en el menú
2. Expande cualquier app
3. Clic **"💾 Backup Manual"**

O desde el menú **Backups → ▶️ Ejecutar Backup**

---

## 7. Seguridad & Anti-Spam {#seguridad}

### Sistema de Roles (RBAC)

| Rol | Acceso |
|-----|--------|
| `admin` | Acceso total: apps, backups, usuarios, spam, config |
| `editor` | Apps, backups, spam rules |
| `viewer` | Solo lectura: dashboard, logs |

### Tipos de Reglas Anti-Spam

| Tipo | Ejemplo | Acción |
|------|---------|--------|
| IP | `192.168.1.100` | block/warn/log |
| Email | `spam@evil.com` | block |
| Dominio | `*.malware.ru` | block |
| User-Agent | `bot-scraper` | block |
| Keyword | `viagra`, `crypto` | block |
| País | `KP`, `IR` | warn |

### Integrar el Logger en tus apps

Agrega al inicio de cada `*.py` de Streamlit:

```python
import sqlite3, datetime, streamlit as st

def log_access(action="view"):
    try:
        conn = sqlite3.connect("../hosting_panel/hosting_jagt.db")
        conn.execute(
            "INSERT INTO access_log(ip,path,action,timestamp,blocked) VALUES(?,?,?,?,0)",
            ("unknown", st.session_state.get("current_page","home"), action,
             datetime.datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except:
        pass  # No interrumpir la app si el log falla

log_access()
```

---

## 8. Disponibilidad 24/7 {#disponibilidad}

### ¿Por qué funciona sin tu PC?

```
Tu PC (solo desarrollo)
    ↓ git push
GitHub (servidor en la nube)
    ↓ webhook automático
Streamlit Cloud (AWS/GCP)
    ↓ build & deploy
Tu app online 24/7
    ↓ cada noche
GitHub Actions
    ↓
Google Drive → hosting-jagt.xlsx actualizado
```

**Streamlit Cloud Free incluye:**
- ✅ 3 apps gratuitas por cuenta
- ✅ HTTPS automático
- ✅ Dominio `.streamlit.app`
- ✅ Auto-restart si la app cae
- ✅ Logs en tiempo real
- ✅ 1 GB de RAM por app

**Para más apps:** usa múltiples cuentas GitHub o considera Streamlit Community Cloud Pro.

---

## 9. Gestión de Aplicaciones {#apps}

### Registrar una nueva app en el panel

1. Menú **"📦 Aplicaciones"**
2. Tab **"➕ Nueva App"**
3. Completa:
   - **Nombre:** nombre descriptivo
   - **Dominio:** URL de Streamlit (ej: `jagt-miapp.streamlit.app`)
   - **Repo:** ruta dentro de `jagt2024/Reservar/` (ej: `mi_app/app.py`)
   - **Descripción, Tech, Backup**
4. Clic **"➕ Registrar App"**

La app queda monitoreada y con backup automático habilitado.

---

## 10. Migración (cuando decidas) {#migracion}

> ⚠️ **No migrar hasta que lo decidas.** El sistema funciona 100% con Streamlit Cloud.

### Opciones de migración futura

| Opción | Costo | Complejidad | Beneficio |
|--------|-------|-------------|-----------|
| VPS (DigitalOcean/Linode) | ~$6/mes | Media | Control total |
| Railway.app | Gratis/~$5 | Baja | Más recursos |
| Render.com | Gratis/~$7 | Baja | Docker support |
| Servidor propio | Hardware | Alta | Máximo control |

### Cuando decidas migrar:

```bash
# El panel ya tiene todos los datos en hosting_jagt.db
# Solo necesitas:
1. Exportar hosting_jagt.db → cp a nuevo servidor
2. Instalar Python + requirements.txt
3. Configurar nginx como proxy
4. Apuntar dominio josegart.* al nuevo servidor
5. El panel y todas las apps funcionan igual
```

---

## 📞 Soporte

- **Email:** josegarjagt@gmail.com
- **GitHub:** github.com/jagt2024
- **Panel:** josegart-hosting.streamlit.app (después del deploy)
- **Excel:** Google Drive → hosting-jagt.xlsx

---

*Documentación generada automáticamente — JAGT Hosting Panel v1.0*  
*Última actualización: Marzo 2026*
