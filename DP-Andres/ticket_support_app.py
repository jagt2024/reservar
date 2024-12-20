import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.graph_objects as go
import json
import toml
import plotly.express as px
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailSender:
    def __init__(self, smtp_server, port, sender_email, password):
        self.smtp_server = smtp_server
        self.port = port
        self.sender_email = sender_email
        self.password = password

    def send_email(self, receiver_email, subject, body):
        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = receiver_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(self.smtp_server, self.port) as server:
            server.starttls()
            server.login(self.sender_email, self.password)
            server.send_message(message)

class TicketGoogleSheets:
    def __init__(self):
        self.creds = self.load_credentials()
        self.sheet_name = 'gestion-reservas-dp'
        self.worksheet_name = 'pqrs'

    def load_credentials(self):
        try:
            with open('./.streamlit/secrets.toml', 'r') as toml_file:
                config = toml.load(toml_file)
                creds = config['sheetsemp']['credentials_sheet']
                if isinstance(creds, str):
                    creds = json.loads(creds)
                return creds
        except Exception as e:
            st.error(f"Error al cargar credenciales: {str(e)}")
            return None

    def _get_worksheet(self):
        try:
            scope = ['https://spreadsheets.google.com/feeds', 
                    'https://www.googleapis.com/auth/drive']
            credentials = Credentials.from_service_account_info(self.creds, scopes=scope)
            client = gspread.authorize(credentials)
            sheet = client.open(self.sheet_name)
            return sheet.worksheet(self.worksheet_name)
        except Exception as e:
            st.error(f"Error al acceder a Google Sheets: {str(e)}")
            return None

    def agregar_ticket(self, fecha, hora, prioridad, estado, descripcion, correo_solicitud):
        worksheet = self._get_worksheet()
        if worksheet:
            try:
                # Obtener el último ID
                data = worksheet.get_all_values()
                next_id = len(data)  # Usar el número de filas como siguiente ID
                
                # Preparar nueva fila
                new_row = [
                    next_id,
                    fecha,
                    hora,
                    prioridad,
                    estado,
                    descripcion,
                    '',  # fecha_cierre inicialmente vacía
                    correo_solicitud
                ]
                
                worksheet.append_row(new_row)
                return next_id
            except Exception as e:
                st.error(f"Error al agregar ticket: {str(e)}")
                return None

    def obtener_tickets_recientes_abiertos(self):
        worksheet = self._get_worksheet()
        if worksheet:
            try:
                data = worksheet.get_all_values()
                headers = data[0]
                df = pd.DataFrame(data[1:], columns=headers)
                
                # Convertir fechas
                df['fecha'] = pd.to_datetime(df['fecha'])
                fecha_limite = datetime.now() - timedelta(days=5)
                
                # Filtrar tickets abiertos recientes
                df = df[
                    (df['estado'] == 'Abierto') & 
                    (df['fecha'] >= fecha_limite)
                ].sort_values(['fecha', 'hora'], ascending=[False, False])
                
                return df
            except Exception as e:
                st.error(f"Error al obtener tickets: {str(e)}")
                return pd.DataFrame()

    def cerrar_ticket(self, ticket_id):
        worksheet = self._get_worksheet()
        if worksheet:
            try:
                # Encontrar la fila del ticket
                cell = worksheet.find(str(ticket_id))
                if cell:
                    row_num = cell.row
                    fecha_cierre = datetime.now().strftime("%Y-%m-%d")
                    
                    # Actualizar estado y fecha de cierre
                    worksheet.update_cell(row_num, 5, 'Cerrado')  # Columna de estado
                    worksheet.update_cell(row_num, 7, fecha_cierre)  # Columna de fecha_cierre
                    return True
            except Exception as e:
                st.error(f"Error al cerrar ticket: {str(e)}")
                return False

class TicketApp:
    def __init__(self):
        self.db = TicketGoogleSheets()
        self.email_sender = EmailSender(
            smtp_server="smtp.gmail.com",
            port=465,
            sender_email=st.secrets['emails']['smtp_user'],
            password=st.secrets['emailsemp']['smtp_password']
        )

    # El resto de los métodos de TicketApp permanecen igual
    def run(self):
        st.title("Sistema de Tickets de Soporte")

        if 'is_support' not in st.session_state:
            st.session_state.is_support = False

        self.login()

        if st.session_state.is_support:
            self.support_view()
        else:
            self.user_view()

    def login(self):
        if not st.session_state.is_support:
            with st.sidebar:
                st.header("Acceso de Soporte")
                password = st.text_input("Contraseña", type="password")
                if st.button("Iniciar sesión"):
                    if password == "soporte4321":
                        st.session_state.is_support = True
                        st.rerun()
                    else:
                        st.error("Contraseña incorrecta")
        else:
            with st.sidebar:
                if st.button("Cerrar sesión"):
                    st.session_state.is_support = False
                    st.rerun()

    def formulario_ticket(self):
        st.header("Agregar Nuevo Ticket")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            fecha = st.date_input("Fecha")
        with col2:
            hora = st.time_input("Hora")
        with col3:
            prioridad = st.selectbox("Prioridad", ["Alta", "Media", "Baja"])
        with col4:
            estado = st.selectbox("Estado", ["Abierto", "En Progreso", "Cerrado"])
        col5, col6 = st.columns(2)
        with col5:
            correo = st.text_input("correo solicitante")
        with col6:
            descripcion = st.text_area("Descripción")

        if st.button("Agregar Ticket"):
            ticket_id = self.db.agregar_ticket(
                fecha.strftime("%Y-%m-%d"),
                hora.strftime("%H:%M"),
                prioridad,
                estado,
                descripcion,
                correo
            )
            if ticket_id:
                st.success("Ticket agregado con éxito!")
                self.enviar_correo_soporte(ticket_id, fecha, hora, prioridad, estado, descripcion, correo)

    def support_view(self):
        self.mostrar_tickets_recientes_abiertos()
        self.filtro_fechas_y_estadisticas()

    def user_view(self):
        self.formulario_ticket()

    def enviar_correo_soporte(self, ticket_id, fecha, hora, prioridad, estado, descripcion, correo):
        subject = f"Nuevo Ticket de Soporte #{ticket_id}"
        body = f"""
        Se ha creado un nuevo ticket de soporte:

        ID: {ticket_id}
        Fecha: {fecha}
        Hora: {hora}
        Prioridad: {prioridad}
        Estado: {estado}
        Descripción: {descripcion}
        correo: {correo}

        Por favor, atender a la brevedad posible.
        """
        
        try:
            self.email_sender.send_email("josegarjagt@gmail.com", subject, body)
            st.success("Correo de notificación enviado a soporte.")
            
            self.email_sender.send_email(str(correo), "Registro solicitud", "Cordial Saludo, hemos recibido su peticion para ser revisada y atendida en el menor tiempo posible por el area de soporte. Gracias por su interes ")
            st.success("Correo de notificación enviado al solicitante.")
            
        except Exception as e:
            st.error(f"Error al enviar correo: {str(e)}")

    def mostrar_tickets_recientes_abiertos(self):
        st.header("Tickets Abiertos (Últimos 5 días)")
        
        df = self.db.obtener_tickets_recientes_abiertos()
        
        if df.empty:
            st.info("No hay tickets abiertos en los últimos 5 días.")
        else:
            for index, row in df.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"Ticket #{row['uid']} - {row['fecha']} {row['hora']} - {row['prioridad']} - {row['estado']}")
                    st.write(f"Descripción: {row['descripcion']}")
                    st.write(f"Corrreo Solicitante: {row['correo_solicitud']}")
                with col2:
                    if st.button(f"Cerrar Ticket #{row['uid']}"):
                        self.db.cerrar_ticket(row['uid'])
                        st.success(f"Ticket #{row['uid']} cerrado con éxito")
                        st.rerun()

        if st.button("Exportar a Excel"):
            current_date = datetime.now().strftime("%Y-%m-%d")
            filename = f"tickets_abiertos_recientes_{current_date}.xlsx"
            df.to_excel(filename, index=False)
            st.success(f"Datos exportados a '{filename}'")

    def filtro_fechas_y_estadisticas(self):
        st.header("Filtro por Fechas y Estadísticas")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha de inicio")
        with col2:
            fecha_fin = st.date_input("Fecha de fin")

        df = self.db.obtener_tickets_recientes_abiertos()
        df['fecha'] = pd.to_datetime(df['fecha'])
        df_filtrado = df[(df['fecha'] >= pd.Timestamp(fecha_inicio)) & (df['fecha'] <= pd.Timestamp(fecha_fin))]

        st.subheader("Tickets Filtrados")
        st.dataframe(df_filtrado)

        st.subheader("Estadísticas")
        fig_prioridad, fig_estado = self.generar_estadisticas(df_filtrado)
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(fig_prioridad, use_container_width=True)
        with col2:
            st.plotly_chart(fig_estado, use_container_width=True)

    @staticmethod
    def generar_estadisticas(df):
        prioridad_counts = df['prioridad'].value_counts()
        estado_counts = df['estado'].value_counts()
        
        fig_prioridad = px.pie(values=prioridad_counts.values, names=prioridad_counts.index, title="Distribución de Prioridades")
        fig_estado = px.pie(values=estado_counts.values, names=estado_counts.index, title="Distribución de Estados")
        
        return fig_prioridad, fig_estado

def soporte():
    app = TicketApp()
    app.run()

#if __name__ == "__main__":
#    soporte()
