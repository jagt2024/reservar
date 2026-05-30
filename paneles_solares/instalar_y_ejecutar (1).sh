#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# SolarCalc Pro — Instalador para macOS / Linux
# ──────────────────────────────────────────────────────────────────────────────

set -e
CYAN='\033[0;36m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
RED='\033[0;31m'; NC='\033[0m'; BOLD='\033[1m'

echo ""
echo -e "${YELLOW}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║         ☀  SOLARCALC PRO — INSTALADOR               ║${NC}"
echo -e "${YELLOW}║         Dimensionamiento Fotovoltaico                 ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Detectar Python ──────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo -e "${RED}[ERROR] Python no encontrado. Instálalo desde https://python.org${NC}"
    exit 1
fi

PY_VER=$($PYTHON --version 2>&1)
echo -e "${GREEN}[OK] $PY_VER${NC}"

# ── Verificar versión mínima 3.8 ────────────────────────────────────────────
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]); then
    echo -e "${RED}[ERROR] Se requiere Python 3.8 o superior.${NC}"
    exit 1
fi

# ── Actualizar pip ───────────────────────────────────────────────────────────
echo -e "${CYAN}[1/4] Actualizando pip...${NC}"
$PYTHON -m pip install --upgrade pip --quiet

# ── Instalar dependencias ────────────────────────────────────────────────────
echo -e "${CYAN}[2/4] Instalando dependencias...${NC}"
$PYTHON -m pip install -r requirements.txt --quiet

echo -e "${CYAN}[3/4] Creando carpeta .streamlit/...${NC}"
mkdir -p .streamlit
if [ -f ".streamlit/config.toml" ]; then
    echo -e "${GREEN}       config.toml ya existe${NC}"
fi

# ── Verificar archivos del proyecto ──────────────────────────────────────────
echo -e "${CYAN}[4/4] Verificando archivos del proyecto...${NC}"
ARCHIVOS=("solar_app.py" "db_utils.py" "modulo_simulador.py" "modulo_presupuesto.py"
          "modulo_materiales.py" "modulo_equipos.py" "modulo_proveedores.py")
FALTANTES=0
for f in "${ARCHIVOS[@]}"; do
    if [ ! -f "$f" ]; then
        echo -e "${RED}  [FALTA] $f${NC}"
        FALTANTES=$((FALTANTES+1))
    else
        echo -e "${GREEN}  [OK]    $f${NC}"
    fi
done

echo ""
if [ "$FALTANTES" -gt 0 ]; then
    echo -e "${YELLOW}[ADVERTENCIA] $FALTANTES archivo(s) no encontrado(s). Verifica la carpeta.${NC}"
else
    echo -e "${GREEN}[OK] Todos los archivos en su lugar.${NC}"
fi

echo ""
echo -e "${YELLOW}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  Instalación completada. Iniciando SolarCalc Pro...  ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Abriendo en: http://localhost:8501${NC}"
echo ""

$PYTHON -m streamlit run solar_app.py
