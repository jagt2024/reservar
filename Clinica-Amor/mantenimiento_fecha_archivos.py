import streamlit as st
import pandas as pd
import toml
import os
from google.oauth2.service_account import Credentials
import gspread
from googleapiclient.discovery import build
from datetime import datetime, timedelta

st.set_page_config(page_title="Mantenimiento de Archivos Google Drive", layout="wide")

def load_credentials():
    """Carga las credenciales desde el archivo de secretos de Streamlit."""
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
        return creds
    except Exception as e:
        st.error(f"Error al cargar credenciales: {str(e)}")
        return None

def get_drive_service():
    """Crea y retorna un servicio de Google Drive."""
    try:
        creds = load_credentials()
        if not creds:
            return None
        
        # Definir el alcance
        scope = ['https://www.googleapis.com/auth/drive']
        
        # Crear credenciales
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        
        # Construir el servicio de Google Drive
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        st.error(f"Error al crear servicio de Drive: {str(e)}")
        return None

def get_sheets_client():
    """Crea y retorna un cliente autorizado de Google Sheets."""
    try:
        creds = load_credentials()
        if not creds:
            return None
        
        # Definir el alcance
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # Crear credenciales
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        
        # Autorizar el cliente
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Error al crear cliente de Sheets: {str(e)}")
        return None

def get_sheet_id_by_name(client, name):
    """Busca el ID de la hoja por su nombre."""
    try:
        sheet_list = client.list_spreadsheet_files()
        for sheet in sheet_list:
            if sheet['name'].lower() == name.lower():
                return sheet['id']
        return None
    except Exception as e:
        st.warning(f"Error al buscar la hoja {name}: {str(e)}")
        return None

def filter_files_by_date(files, start_date=None, end_date=None, date_field='modifiedTime'):
    """Filtra archivos por rango de fechas."""
    if not start_date and not end_date:
        return files
    
    filtered_files = []
    
    for file in files:
        if not file.get(date_field):
            continue
        
        # Convertir fecha del archivo a formato datetime
        file_date_str = file.get(date_field).split('T')[0]  # Tomar solo la parte de la fecha
        file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
        
        # Verificar si está dentro del rango
        if start_date and end_date:
            if start_date <= file_date <= end_date:
                filtered_files.append(file)
        elif start_date:
            if start_date <= file_date:
                filtered_files.append(file)
        elif end_date:
            if file_date <= end_date:
                filtered_files.append(file)
    
    return filtered_files

def list_files(service, folder_id=None, query=None, start_date=None, end_date=None, date_field='modifiedTime'):
    """Lista archivos en Google Drive, opcionalmente filtrados por carpeta, consulta o fechas."""
    try:
        if folder_id:
            q = f"'{folder_id}' in parents"
        elif query:
            q = query
        else:
            q = "trashed=false"
        
        # Aplicar filtros de fecha en la consulta API si es posible
        if start_date and date_field:
            start_date_str = start_date.strftime("%Y-%m-%dT00:00:00")
            q += f" and {date_field} >= '{start_date_str}'"
        
        if end_date and date_field:
            # Añadir un día para incluir todo el día final
            end_date_with_time = (end_date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
            q += f" and {date_field} <= '{end_date_with_time}'"
        
        results = service.files().list(
            q=q,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, owners, webViewLink)"
        ).execute()
        
        files = results.get('files', [])
        
        # Para casos donde no podemos filtrar por fecha en la consulta API
        if (start_date or end_date) and not date_field:
            files = filter_files_by_date(files, start_date, end_date)
            
        return files
    except Exception as e:
        st.error(f"Error al listar archivos: {str(e)}")
        return []

def format_size(size):
    """Formatea el tamaño de un archivo en un formato legible."""
    try:
        size = int(size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    except:
        return "N/A"

def list_folders(service):
    """Lista las carpetas en Google Drive."""
    try:
        return list_files(service, query="mimeType='application/vnd.google-apps.folder' and trashed=false")
    except Exception as e:
        st.error(f"Error al listar carpetas: {str(e)}")
        return []

def update_file_metadata(service, file_id, metadata):
    """Actualiza los metadatos de un archivo."""
    try:
        return service.files().update(fileId=file_id, body=metadata).execute()
    except Exception as e:
        st.error(f"Error al actualizar metadatos: {str(e)}")
        return None

def move_file(service, file_id, folder_id):
    """Mueve un archivo a una carpeta específica."""
    try:
        # Obtener padres actuales
        file = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        
        # Mover a la nueva carpeta
        file = service.files().update(
            fileId=file_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        
        return file
    except Exception as e:
        st.error(f"Error al mover archivo: {str(e)}")
        return None

def copy_file(service, file_id, new_name=None):
    """Crea una copia de un archivo."""
    try:
        body = {}
        if new_name:
            body['name'] = new_name
            
        return service.files().copy(fileId=file_id, body=body).execute()
    except Exception as e:
        st.error(f"Error al copiar archivo: {str(e)}")
        return None

def trash_file(service, file_id):
    """Envía un archivo a la papelera."""
    try:
        return service.files().update(fileId=file_id, body={'trashed': True}).execute()
    except Exception as e:
        st.error(f"Error al enviar archivo a papelera: {str(e)}")
        return None

def restore_file(service, file_id):
    """Restaura un archivo de la papelera."""
    try:
        return service.files().update(fileId=file_id, body={'trashed': False}).execute()
    except Exception as e:
        st.error(f"Error al restaurar archivo: {str(e)}")
        return None

def permanently_delete_file(service, file_id):
    """Elimina un archivo permanentemente."""
    try:
        service.files().delete(fileId=file_id).execute()
        return True
    except Exception as e:
        st.error(f"Error al eliminar archivo permanentemente: {str(e)}")
        return False

def search_files(service, query_text, start_date=None, end_date=None, date_field='modifiedTime'):
    """Busca archivos por nombre y opcionalmente filtra por fecha."""
    try:
        q = f"name contains '{query_text}' and trashed=false"
        return list_files(service, query=q, start_date=start_date, end_date=end_date, date_field=date_field)
    except Exception as e:
        st.error(f"Error en la búsqueda: {str(e)}")
        return []

def display_file_details(service, file_id):
    """Muestra detalles detallados de un archivo seleccionado."""
    try:
        file = service.files().get(
            fileId=file_id,
            fields='id, name, mimeType, createdTime, modifiedTime, size, owners, description, webViewLink, parents'
        ).execute()
        
        st.subheader(f"Detalles del archivo: {file.get('name')}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**ID:** {file.get('id')}")
            st.write(f"**Tipo:** {file.get('mimeType')}")
            st.write(f"**Tamaño:** {format_size(file.get('size', 'N/A'))}")
            st.write(f"**Creado:** {file.get('createdTime')}")
            
        with col2:
            st.write(f"**Modificado:** {file.get('modifiedTime')}")
            owners = file.get('owners', [])
            if owners:
                st.write(f"**Propietario:** {owners[0].get('displayName')}")
            st.write(f"**Enlace:** [Abrir archivo]({file.get('webViewLink')})")
        
        st.divider()
        
        # Acciones del archivo
        st.subheader("Acciones")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🗑️ Enviar a papelera", key=f"trash_{file_id}"):
                if trash_file(service, file_id):
                    st.success("Archivo enviado a la papelera")
                    st.rerun()
        
        with col2:
            new_name = st.text_input("Nuevo nombre:", value=file.get('name'), key=f"rename_{file_id}")
            if st.button("✏️ Renombrar", key=f"rename_btn_{file_id}"):
                if update_file_metadata(service, file_id, {'name': new_name}):
                    st.success(f"Archivo renombrado a {new_name}")
                    st.rerun()
        
        with col3:
            copy_name = st.text_input("Nombre de la copia:", value=f"Copia de {file.get('name')}", key=f"copy_{file_id}")
            if st.button("📋 Crear copia", key=f"copy_btn_{file_id}"):
                if copy_file(service, file_id, copy_name):
                    st.success("Copia creada exitosamente")
                    st.rerun()
        
        # Mover a otra carpeta
        st.subheader("Mover a otra carpeta")
        folders = list_folders(service)
        folder_names = [folder.get('name') for folder in folders]
        selected_folder = st.selectbox("Seleccionar carpeta destino:", folder_names, key=f"move_{file_id}")
        
        if st.button("📁 Mover archivo", key=f"move_btn_{file_id}"):
            selected_folder_id = next((folder.get('id') for folder in folders if folder.get('name') == selected_folder), None)
            if selected_folder_id:
                if move_file(service, file_id, selected_folder_id):
                    st.success(f"Archivo movido a {selected_folder}")
                    st.rerun()
    
    except Exception as e:
        st.error(f"Error al mostrar detalles del archivo: {str(e)}")

def date_filter_section():
    """Sección para filtros de fecha."""
    st.sidebar.subheader("Filtrar por fecha")
    date_field = st.sidebar.selectbox(
        "Campo de fecha:",
        [("Fecha de modificación", "modifiedTime"), ("Fecha de creación", "createdTime")],
        format_func=lambda x: x[0]
    )
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Desde:", value=None)
    with col2:
        end_date = st.date_input("Hasta:", value=None)
    
    return start_date, end_date, date_field[1] if date_field else "modifiedTime"

def main():
    st.title("Mantenimiento de Archivos de Google Drive")
    
    # Inicializar servicios
    drive_service = get_drive_service()
    sheets_client = get_sheets_client()
    
    if not drive_service or not sheets_client:
        st.error("No se pudieron inicializar los servicios. Verifica las credenciales.")
        return
    
    # Sidebar para navegación
    st.sidebar.title("Navegación")
    menu = st.sidebar.radio(
        "Selecciona una opción:",
        ["📁 Explorador de archivos", "🗑️ Papelera", "🔍 Búsqueda avanzada", "📊 Panel de uso"]
    )
    
    # Filtradores de fecha comunes a todas las secciones
    start_date, end_date, date_field = date_filter_section()
    
    if menu == "📁 Explorador de archivos":
        st.header("Explorador de archivos")
        
        # Obtener carpetas para el selector
        folders = list_folders(drive_service)
        folder_options = ["Raíz"] + [folder.get('name') for folder in folders]
        
        selected_folder = st.selectbox("Seleccionar carpeta:", folder_options)
        
        # Determinar qué archivos mostrar
        if selected_folder == "Raíz":
            files = list_files(drive_service, start_date=start_date, end_date=end_date, date_field=date_field)
        else:
            folder_id = next((folder.get('id') for folder in folders if folder.get('name') == selected_folder), None)
            if folder_id:
                files = list_files(drive_service, folder_id=folder_id, start_date=start_date, end_date=end_date, date_field=date_field)
            else:
                st.warning("Carpeta no encontrada")
                files = []
        
        # Mostrar archivos en una tabla
        if files:
            st.success(f"Se encontraron {len(files)} archivos en el rango de fechas seleccionado.")
            
            df = pd.DataFrame([{
                'Nombre': file.get('name'),
                'Tipo': file.get('mimeType').split('.')[-1] if file.get('mimeType') else 'Desconocido',
                'Modificado': file.get('modifiedTime').split('T')[0] if file.get('modifiedTime') else 'N/A',
                'Creado': file.get('createdTime').split('T')[0] if file.get('createdTime') else 'N/A',
                'Tamaño': format_size(file.get('size')) if file.get('size') else 'N/A',
                'ID': file.get('id')
            } for file in files])
            
            # Agregar columna para ver detalles
            # Create a unique key for each row
            df['key'] = [f"file_{i}" for i in range(len(df))]
            st.dataframe(df.drop(columns=['key']), hide_index=True, column_config={'ID': None})

            # Then handle selection with a selectbox
            selected_file = st.selectbox("Seleccionar archivo para ver detalles:", 
                             options=df['Nombre'].tolist(),
                             index=None)

            if selected_file:
                file_id = df.loc[df['Nombre'] == selected_file, 'ID'].iloc[0]
                display_file_details(drive_service, file_id)          

            # Manejar clics en botones
            if st.session_state.get('dataframe_clicked_row'):
                row = st.session_state['dataframe_clicked_row']
                if row.get('Acciones') == 'Ver detalles':
                    file_id = df.loc[df['Nombre'] == row.get('Nombre'), 'ID'].iloc[0]
                    display_file_details(drive_service, file_id)
        else:
            st.info("No se encontraron archivos en esta ubicación o rango de fechas.")
    
    elif menu == "🗑️ Papelera":
        st.header("Papelera")
        
        # Obtener archivos en papelera con filtro de fechas
        trash_files = list_files(drive_service, query="trashed=true", 
                                 start_date=start_date, end_date=end_date, date_field=date_field)
        
        if trash_files:
            st.success(f"Se encontraron {len(trash_files)} archivos en la papelera en el rango de fechas seleccionado.")
            
            df = pd.DataFrame([{
                'Nombre': file.get('name'),
                'Tipo': file.get('mimeType').split('.')[-1] if file.get('mimeType') else 'Desconocido',
                'Modificado': file.get('modifiedTime').split('T')[0] if file.get('modifiedTime') else 'N/A',
                'Creado': file.get('createdTime').split('T')[0] if file.get('createdTime') else 'N/A',
                'ID': file.get('id')
            } for file in trash_files])
            
            # Mostrar tabla de archivos en papelera
            selected_files = st.multiselect(
                "Selecciona archivos para restaurar o eliminar:",
                df['Nombre'].tolist()
            )
            
            if selected_files:
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🔄 Restaurar seleccionados"):
                        for name in selected_files:
                            file_id = df.loc[df['Nombre'] == name, 'ID'].iloc[0]
                            if restore_file(drive_service, file_id):
                                st.success(f"Restaurado: {name}")
                        st.rerun()
                
                with col2:
                    if st.button("⚠️ Eliminar permanentemente"):
                        confirm = st.checkbox("Confirmar eliminación permanente")
                        if confirm:
                            for name in selected_files:
                                file_id = df.loc[df['Nombre'] == name, 'ID'].iloc[0]
                                if permanently_delete_file(drive_service, file_id):
                                    st.success(f"Eliminado: {name}")
                            st.rerun()
            
            # Mostrar la tabla
            st.dataframe(df, hide_index=True, column_config={'ID': None})
        else:
            st.info("No se encontraron archivos en la papelera para el rango de fechas seleccionado.")
    
    elif menu == "🔍 Búsqueda avanzada":
        st.header("Búsqueda avanzada")
        
        search_query = st.text_input("Buscar archivos por nombre:")
        
        if search_query:
            search_results = search_files(drive_service, search_query, 
                                         start_date=start_date, end_date=end_date, date_field=date_field)
            
            if search_results:
                st.success(f"Se encontraron {len(search_results)} resultado(s) para '{search_query}' en el rango de fechas seleccionado.")
                
                df = pd.DataFrame([{
                    'Nombre': file.get('name'),
                    'Tipo': file.get('mimeType').split('.')[-1] if file.get('mimeType') else 'Desconocido',
                    'Modificado': file.get('modifiedTime').split('T')[0] if file.get('modifiedTime') else 'N/A',
                    'Creado': file.get('createdTime').split('T')[0] if file.get('createdTime') else 'N/A',
                    'Tamaño': format_size(file.get('size')) if file.get('size') else 'N/A',
                    'ID': file.get('id'),
                    'Acciones': 'Ver detalles'
                } for file in search_results])
                
                # Mostrar la tabla
                # Create a unique key for each row
                df['key'] = [f"file_{i}" for i in range(len(df))]
                st.dataframe(df.drop(columns=['key']), hide_index=True, column_config={'ID': None})

                # Then handle selection with a selectbox
                selected_file = st.selectbox("Seleccionar archivo para ver detalles:", 
                             options=df['Nombre'].tolist(),
                             index=None)

                if selected_file:
                    file_id = df.loc[df['Nombre'] == selected_file, 'ID'].iloc[0]
                    display_file_details(drive_service, file_id)
                
                # Manejar clics en botones
                if st.session_state.get('dataframe_clicked_row'):
                    row = st.session_state['dataframe_clicked_row']
                    if row.get('Acciones') == 'Ver detalles':
                        file_id = df.loc[df['Nombre'] == row.get('Nombre'), 'ID'].iloc[0]
                        display_file_details(drive_service, file_id)
            else:
                st.info(f"No se encontraron resultados para '{search_query}' en el rango de fechas seleccionado.")
    
    elif menu == "📊 Panel de uso":
        st.header("Panel de uso de Google Drive")
        
        # Obtener todos los archivos con filtro de fechas
        all_files = list_files(drive_service, start_date=start_date, end_date=end_date, date_field=date_field)
        
        if all_files:
            st.success(f"Analizando {len(all_files)} archivos en el rango de fechas seleccionado.")
            
            # Estadísticas generales
            total_files = len(all_files)
            
            # Calcular tamaño total
            total_size = sum(int(file.get('size', 0)) for file in all_files if file.get('size'))
            
            # Tipos de archivo
            file_types = {}
            for file in all_files:
                mime_type = file.get('mimeType', 'unknown').split('.')[-1]
                file_types[mime_type] = file_types.get(mime_type, 0) + 1
            
            # Fechas de modificación
            mod_dates = {}
            for file in all_files:
                if file.get('modifiedTime'):
                    date = file.get('modifiedTime').split('T')[0]
                    mod_dates[date] = mod_dates.get(date, 0) + 1
            
            # Mostrar estadísticas
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Total de archivos", total_files)
                st.metric("Tamaño total", format_size(total_size))
                
                # Añadir rango de fechas
                if start_date and end_date:
                    st.write(f"**Periodo analizado:** Del {start_date} al {end_date}")
                elif start_date:
                    st.write(f"**Periodo analizado:** Desde {start_date}")
                elif end_date:
                    st.write(f"**Periodo analizado:** Hasta {end_date}")
            
            with col2:
                # Seleccionar los 5 tipos más comunes
                top_types = sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:5]
                st.write("**Tipos de archivo más comunes:**")
                for tipo, count in top_types:
                    st.write(f"- {tipo}: {count} archivos")
            
            # Gráficos
            st.subheader("Distribución por tipo de archivo")
            
            # Preparar datos para el gráfico de tipos
            type_df = pd.DataFrame({
                'Tipo': list(file_types.keys()),
                'Cantidad': list(file_types.values())
            })
            
            # Mostrar gráfico de tipos
            st.bar_chart(type_df.set_index('Tipo'))
            
            # Gráfico de actividad
            st.subheader("Actividad en el periodo (archivos modificados)")
            
            # Preparar datos para el gráfico de fechas
            if mod_dates:
                date_df = pd.DataFrame({
                    'Fecha': list(mod_dates.keys()),
                    'Archivos': list(mod_dates.values())
                })
                
                # Ordenar por fecha
                date_df['Fecha'] = pd.to_datetime(date_df['Fecha'])
                date_df = date_df.sort_values('Fecha')
                
                # Mostrar gráfico de actividad
                st.line_chart(date_df.set_index('Fecha'))
            else:
                st.info("No hay datos de actividad para mostrar en este rango de fechas.")
            
            # Archivos más grandes
            st.subheader("Archivos más grandes en el periodo")
            
            # Filtrar archivos con tamaño
            files_with_size = [file for file in all_files if file.get('size')]
            
            # Ordenar por tamaño
            largest_files = sorted(files_with_size, key=lambda x: int(x.get('size', 0)), reverse=True)[:10]
            
            if largest_files:
                # Crear dataframe
                largest_df = pd.DataFrame([{
                    'Nombre': file.get('name'),
                    'Tamaño': format_size(file.get('size')),
                    'Tipo': file.get('mimeType').split('.')[-1] if file.get('mimeType') else 'Desconocido',
                    'Fecha de modificación': file.get('modifiedTime').split('T')[0] if file.get('modifiedTime') else 'N/A',
                    'Enlace': file.get('webViewLink', '#')
                } for file in largest_files])
                
                # Mostrar tabla
                st.dataframe(largest_df, hide_index=True, column_config={
                    'Enlace': st.column_config.LinkColumn()
                })
            else:
                st.info("No hay archivos con información de tamaño en este periodo.")
            
        else:
            st.info("No se encontraron archivos para el rango de fechas seleccionado.")

if __name__ == "__main__":
    main()
