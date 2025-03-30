import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from io import BytesIO
import base64
import hashlib
import datetime
import uuid
import os
from cryptography.fernet import Fernet

# Configuración de la página
#st.set_page_config(
#    page_title="Sistema de Protección de Datos Sensibles",
#    page_icon="🔒",
#    layout="wide"
#)

# Funciones de cifrado y seguridad
def generar_clave():
    """Genera una clave para el cifrado de datos"""
    if 'clave_cifrado' not in st.session_state:
        clave = Fernet.generate_key()
        st.session_state['clave_cifrado'] = clave
    return st.session_state['clave_cifrado']

def cifrar_texto(texto, clave):
    """Cifra un texto usando Fernet"""
    if not texto:
        return ""
    f = Fernet(clave)
    texto_bytes = texto.encode('utf-8')
    return f.encrypt(texto_bytes)

def descifrar_texto(texto_cifrado, clave):
    """Descifra un texto usando Fernet"""
    if not texto_cifrado:
        return ""
    f = Fernet(clave)
    return f.decrypt(texto_cifrado).decode('utf-8')

def anonimizar_datos(dato, metodo='hash'):
    """Anonimiza datos usando diferentes métodos"""
    if not dato:
        return ""
    
    if metodo == 'hash':
        return hashlib.sha256(str(dato).encode()).hexdigest()[:10]
    elif metodo == 'mascara':
        dato_str = str(dato)
        if len(dato_str) <= 4:
            return "*" * len(dato_str)
        return dato_str[:2] + "*" * (len(dato_str) - 4) + dato_str[-2:]
    return dato

def crear_log_acceso(accion, datos_accedidos):
    """Registra accesos a datos sensibles"""
    ahora = datetime.datetime.now()
    registro = {
        'timestamp': ahora.strftime("%Y-%m-%d %H:%M:%S"),
        'accion': accion,
        'datos_accedidos': datos_accedidos,
        'id_sesion': st.session_state.get('id_sesion', 'desconocido')
    }
    
    if 'log_accesos' not in st.session_state:
        st.session_state['log_accesos'] = []
    
    st.session_state['log_accesos'].append(registro)

# Inicialización de sesión
if 'id_sesion' not in st.session_state:
    st.session_state['id_sesion'] = str(uuid.uuid4())

if 'datos_sensibles' not in st.session_state:
    st.session_state['datos_sensibles'] = pd.DataFrame(columns=[
        'Nombre', 'Apellido', 'DNI/NIF', 'Email', 
        'Teléfono', 'Dirección', 'Fecha_Nacimiento'
    ])

# Clave de cifrado para la sesión
clave_cifrado = generar_clave()

# Función para generar PDF
def generar_pdf(datos, metadatos, incluir_log=False):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    elements = []
    
    # Título y metadatos
    elements.append(Paragraph("Informe de Datos Protegidos", styles['Title']))
    elements.append(Paragraph(f"Fecha de generación: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Paragraph(f"ID de informe: {uuid.uuid4()}", styles['Normal']))
    elements.append(Paragraph("Este documento contiene información protegida según normativa de protección de datos.", styles['Normal']))
    
    for key, value in metadatos.items():
        elements.append(Paragraph(f"{key}: {value}", styles['Normal']))
    
    elements.append(Paragraph(" ", styles['Normal']))  # Espacio
    
    # Datos anonimizados/protegidos
    elements.append(Paragraph("Datos registrados (protegidos):", styles['Heading2']))
    
    # Convertir DataFrame a tabla para PDF
    if not datos.empty:
        data = [datos.columns.tolist()]
        data.extend(datos.values.tolist())
        
        tabla = Table(data)
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(tabla)
    
    # Añadir log de accesos si se solicita
    if incluir_log and 'log_accesos' in st.session_state:
        elements.append(Paragraph(" ", styles['Normal']))  # Espacio
        elements.append(Paragraph("Registro de Accesos:", styles['Heading2']))
        
        log_data = [['Timestamp', 'Acción', 'Datos Accedidos', 'ID Sesión']]
        for log in st.session_state['log_accesos']:
            log_data.append([
                log['timestamp'],
                log['accion'],
                log['datos_accedidos'],
                log['id_sesion']
            ])
        
        log_table = Table(log_data)
        log_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(log_table)
    
    # Añadir pie de página con información de cumplimiento
    elements.append(Paragraph(" ", styles['Normal']))  # Espacio
    elements.append(Paragraph("Este documento cumple con las normativas de protección de datos personales. Los datos sensibles han sido tratados según los principios de privacidad por diseño y por defecto.", styles['Normal']))
    
    # Construir el PDF
    doc.build(elements)
    return buffer

# Interfaz de usuario con Streamlit
#st.title("🔒 Sistema de Protección de Datos Sensibles")

# Sidebar para opciones
st.sidebar.header("Configuración")
modo_anonimizacion = st.sidebar.selectbox(
    "Método de anonimización",
    ["hash", "mascara", "cifrado completo"]
)

st.sidebar.subheader("Cumplimiento Normativo")
normativa_seleccionada = st.sidebar.multiselect(
    "Normativas aplicables",
    ["Ley 1581 (Colombia)", "RGPD (UE)", "LOPD-GDD (España)", "CCPA (California)", "LGPD (Brasil)"],
    default=["Ley 1581 (Colombia)"]
)

st.sidebar.subheader("Opciones de exportación")
incluir_log_en_pdf = st.sidebar.checkbox("Incluir registro de accesos en PDF", value=True)
incluir_metadatos = st.sidebar.checkbox("Incluir metadatos de cumplimiento", value=True)

# Pestañas principales
tab1, tab2, tab3, tab4 = st.tabs(["Registro de Datos", "Visualización Segura", "Exportar a PDF", "Información Normativa"])

# Pestaña de registro de datos
with tab1:
    st.header("Registro de Datos Sensibles")
    st.write("Complete el formulario para registrar datos sensibles. Estos serán protegidos según la configuración seleccionada.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        nombre = st.text_input("Nombre")
        apellido = st.text_input("Apellido")
        dni = st.text_input("Documento de Identidad")
        email = st.text_input("Email")
    
    with col2:
        telefono = st.text_input("Teléfono")
        direccion = st.text_input("Dirección")
        fecha_nacimiento = st.date_input("Fecha de Nacimiento")
    
    if st.button("Registrar Datos",key='boton1'):
        if nombre and apellido and dni:
            # Procesar datos según el método seleccionado
            nuevo_registro = {
                'Nombre': nombre,
                'Apellido': apellido,
                'DNI/NIF': dni,
                'Email': email,
                'Teléfono': telefono,
                'Dirección': direccion,
                'Fecha_Nacimiento': fecha_nacimiento.strftime("%Y-%m-%d") if fecha_nacimiento else ""
            }
            
            # Si se selecciona cifrado completo, cifrar los datos
            if modo_anonimizacion == "cifrado completo":
                for campo, valor in nuevo_registro.items():
                    if valor:
                        nuevo_registro[campo] = base64.b64encode(cifrar_texto(str(valor), clave_cifrado)).decode('utf-8')
            else:
                # Aplicar anonimización a campos sensibles
                campos_sensibles = ['DNI/NIF', 'Email', 'Teléfono', 'Dirección']
                for campo in campos_sensibles:
                    if nuevo_registro[campo]:
                        nuevo_registro[campo] = anonimizar_datos(nuevo_registro[campo], modo_anonimizacion)
            
            # Añadir a DataFrame
            st.session_state['datos_sensibles'] = pd.concat([
                st.session_state['datos_sensibles'],
                pd.DataFrame([nuevo_registro])
            ], ignore_index=True)
            
            crear_log_acceso("registro_datos", f"Registro de datos para {nombre} {apellido}")
            st.success("Datos registrados con éxito y protegidos según la configuración")
        else:
            st.error("Por favor complete al menos Nombre, Apellido y Documento de Identidad")

# Pestaña de visualización
with tab2:
    st.header("Visualización Segura de Datos")
    
    if st.session_state['datos_sensibles'].empty:
        st.info("No hay datos registrados aún")
    else:
        st.write("Datos registrados (con protección aplicada):")
        st.dataframe(st.session_state['datos_sensibles'])
        
        # Opción para ver datos específicos con autorización
        st.subheader("Acceso a datos específicos")
        
        col1, col2 = st.columns(2)
        with col1:
            indice_seleccionado = st.number_input("Seleccione índice de registro a consultar", 
                                                min_value=0, 
                                                max_value=len(st.session_state['datos_sensibles'])-1 if not st.session_state['datos_sensibles'].empty else 0,
                                                step=1)
        
        with col2:
            motivo_consulta = st.text_input("Motivo de la consulta (obligatorio para registro)")
        
        if st.button("Consultar registro completo",key='boton2') and not st.session_state['datos_sensibles'].empty and motivo_consulta:
            registro = st.session_state['datos_sensibles'].iloc[indice_seleccionado].to_dict()
            
            # Si los datos están cifrados, intentar descifrarlos
            if modo_anonimizacion == "cifrado completo":
                for campo, valor in registro.items():
                    try:
                        if valor and isinstance(valor, str):
                            valor_bytes = base64.b64decode(valor)
                            registro[campo] = descifrar_texto(valor_bytes, clave_cifrado)
                    except:
                        pass  # Si falla el descifrado, mantener el valor original
            
            crear_log_acceso("consulta_detallada", f"Consulta del registro {indice_seleccionado}. Motivo: {motivo_consulta}")
            st.json(registro)
        elif st.button("Consultar registro completo") and not motivo_consulta:
            st.warning("Debe proporcionar un motivo para la consulta")

# Pestaña de exportación a PDF
with tab3:
    st.header("Exportar Datos a PDF Seguro")
    
    col1, col2 = st.columns(2)
    
    with col1:
        nombre_informe = st.text_input("Nombre del informe", "Informe_Datos_Protegidos")
    
    with col2:
        finalidad_informe = st.text_input("Finalidad del informe", "Cumplimiento normativo")
    
    metadatos = {
        "Finalidad": finalidad_informe,
        "Normativas aplicadas": ", ".join(normativa_seleccionada),
        "Método de protección": modo_anonimizacion,
        "Responsable": st.session_state.get('id_sesion', 'No identificado')
    }
    
    if st.button("Generar PDF",key='boton4'):
        if st.session_state['datos_sensibles'].empty:
            st.warning("No hay datos para exportar")
        else:
            crear_log_acceso("exportar_pdf", f"Generación de PDF: {nombre_informe}")
            
            # Generar PDF
            pdf_buffer = generar_pdf(
                st.session_state['datos_sensibles'],
                metadatos,
                incluir_log_en_pdf
            )
            
            # Convertir a base64 para descargar
            b64 = base64.b64encode(pdf_buffer.getvalue()).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="{nombre_informe}.pdf">Descargar informe PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            
            st.success("Informe PDF generado exitosamente")

# Pestaña de información normativa
with tab4:
    st.header("Información sobre Normativas de Protección de Datos")
    
    normativas = {
        "Ley 1581 (Colombia)": {
            "Descripción": "Ley Estatutaria 1581 de 2012 - Protección de Datos Personales en Colombia",
            "Principios clave": [
                "Principio de legalidad en materia de tratamiento de datos",
                "Principio de finalidad",
                "Principio de libertad",
                "Principio de veracidad o calidad",
                "Principio de transparencia",
                "Principio de acceso y circulación restringida",
                "Principio de seguridad",
                "Principio de confidencialidad"
            ],
            "Derechos del titular": [
                "Conocer, actualizar y rectificar sus datos personales",
                "Solicitar prueba de la autorización otorgada al responsable",
                "Ser informado sobre el uso que se ha dado a sus datos personales",
                "Revocar la autorización y/o solicitar la supresión del dato",
                "Acceder en forma gratuita a sus datos personales"
            ],
            "Enlace": "https://www.sic.gov.co/sites/default/files/normatividad/Ley_1581_2012.pdf"
        },
        "RGPD (UE)": {
            "Descripción": "Reglamento General de Protección de Datos de la Unión Europea",
            "Principios clave": [
                "Licitud, lealtad y transparencia",
                "Limitación de la finalidad",
                "Minimización de datos",
                "Exactitud",
                "Limitación del plazo de conservación",
                "Integridad y confidencialidad",
                "Responsabilidad proactiva"
            ],
            "Enlace": "https://gdpr.eu/"
        },
        "LOPD-GDD (España)": {
            "Descripción": "Ley Orgánica de Protección de Datos y Garantía de los Derechos Digitales",
            "Principios clave": [
                "Adaptación del RGPD al contexto español",
                "Garantía de derechos digitales",
                "Tratamiento de datos de menores",
                "Consentimiento digital"
            ],
            "Enlace": "https://www.boe.es/buscar/doc.php?id=BOE-A-2018-16673"
        },
        "CCPA (California)": {
            "Descripción": "California Consumer Privacy Act",
            "Principios clave": [
                "Derecho a saber qué información personal se recopila",
                "Derecho a eliminar información personal",
                "Derecho a excluirse de la venta de información personal",
                "Derecho a no ser discriminado por ejercer los derechos de privacidad"
            ],
            "Enlace": "https://oag.ca.gov/privacy/ccpa"
        },
        "LGPD (Brasil)": {
            "Descripción": "Lei Geral de Proteção de Dados",
            "Principios clave": [
                "Respeto a la privacidad",
                "Autodeterminación informativa",
                "Libertad de expresión, información, comunicación y opinión",
                "Inviolabilidad de la intimidad, honor e imagen",
                "Desarrollo económico y tecnológico e innovación",
                "Libre iniciativa, libre competencia y defensa del consumidor"
            ],
            "Enlace": "https://www.gov.br/cidadania/pt-br/acesso-a-informacao/lgpd"
        }
    }
    
    for normativa, info in normativas.items():
        if normativa in normativa_seleccionada:
            st.subheader(normativa)
            st.write(info["Descripción"])
            
            st.write("**Principios clave:**")
            for principio in info["Principios clave"]:
                st.write(f"- {principio}")
            
            # Mostrar derechos del titular para la normativa colombiana
            if normativa == "Ley 1581 (Colombia)" and "Derechos del titular" in info:
                st.write("**Derechos del titular de los datos:**")
                for derecho in info["Derechos del titular"]:
                    st.write(f"- {derecho}")
    
    st.subheader("Buenas prácticas implementadas en este sistema")
    st.write("""
    - **Minimización de datos**: Solo se recopilan los datos necesarios.
    - **Cifrado y anonimización**: Protección de datos sensibles mediante diferentes técnicas.
    - **Registro de accesos**: Auditoría de quién accede a qué información y por qué.
    - **Transparencia**: Información clara sobre el tratamiento de datos.
    - **Exportación segura**: Generación de documentos con metadatos de cumplimiento.
    - **Autorización**: Registro del motivo de consulta de datos personales.
    - **Trazabilidad**: Sistema de logs para auditoría de operaciones.
    """)
    
    # Información específica sobre la Superintendencia de Industria y Comercio (SIC) de Colombia
    if "Ley 1581 (Colombia)" in normativa_seleccionada:
        st.subheader("Autoridad de Protección de Datos en Colombia")
        st.write("""
        La **Superintendencia de Industria y Comercio (SIC)** es la autoridad de protección de datos en Colombia.
        
        Funciones principales:
        - Garantizar el cumplimiento de la legislación en materia de protección de datos personales
        - Adelantar investigaciones e imponer sanciones
        - Promover y divulgar los derechos de los titulares
        - Emitir instrucciones sobre medidas de seguridad en el tratamiento de datos personales
        
        Para más información o presentar una queja, visite: [Superintendencia de Industria y Comercio](https://www.sic.gov.co/)
        """)

# Footer
#st.markdown("---")
#st.caption("Sistema de Protección de Datos Sensibles | Desarrollado con Streamlit")
