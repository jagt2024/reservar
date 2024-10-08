import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
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

class TicketDatabase:
    def __init__(self, db_name='tickets.db'):
        self.conn = sqlite3.connect(db_name)
        self.c = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.c.execute('''CREATE TABLE IF NOT EXISTS tickets
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          fecha TEXT,
                          hora TEXT,
                          prioridad TEXT,
                          estado TEXT,
                          descripcion TEXT,
                          fecha_cierre TEXT)''')
        self.conn.commit()

    def agregar_ticket(self, fecha, hora, prioridad, estado, descripcion):
        self.c.execute("INSERT INTO tickets (fecha, hora, prioridad, estado, descripcion, fecha_cierre) VALUES (?, ?, ?, ?, ?, ?)",
                       (fecha, hora, prioridad, estado, descripcion, None))
        self.conn.commit()
        return self.c.lastrowid

    def obtener_tickets_recientes_abiertos(self):
        fecha_limite = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        query = """
        SELECT * FROM tickets 
        WHERE estado = 'Abierto' AND fecha >= ?
        ORDER BY fecha DESC, hora DESC
        """
        return pd.read_sql_query(query, self.conn, params=(fecha_limite,))

    def cerrar_ticket(self, ticket_id):
        fecha_cierre = datetime.now().strftime("%Y-%m-%d")
        self.c.execute("UPDATE tickets SET estado = 'Cerrado', fecha_cierre = ? WHERE id = ?", (fecha_cierre, ticket_id))
        self.conn.commit()

    def close(self):
        self.conn.close()

class TicketApp:
    def __init__(self):
        self.db = TicketDatabase()
        self.email_sender = EmailSender(
            smtp_server="smtp.gmail.com",
            port=465,
            sender_email=st.secrets['emails']['smtp_user'],
            password=st.secrets['emailsemp']['smtp_password']
        )

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
                    if password == "soporte4321":  # Reemplaza con una contraseña segura
                        st.session_state.is_support = True
                        st.rerun()
                    else:
                        st.error("Contraseña incorrecta")
        else:
            with st.sidebar:
                if st.button("Cerrar sesión"):
                    st.session_state.is_support = False
                    st.rerun()

    def user_view(self):
        self.formulario_ticket()

    def support_view(self):
        self.mostrar_tickets_recientes_abiertos()
        self.filtro_fechas_y_estadisticas()

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
            descripcion = st.text_area("Descripción:(de ser posible copiar el error generado si se presento.)")

        if st.button("Agregar Ticket"):
            ticket_id = self.db.agregar_ticket(fecha.strftime("%Y-%m-%d"), hora.strftime("%H:%M"), prioridad, estado, descripcion)
            st.success("Ticket agregado con éxito!")
            self.enviar_correo_soporte(ticket_id, fecha, hora, prioridad, estado, descripcion)

    def enviar_correo_soporte(self, ticket_id, fecha, hora, prioridad, estado, descripcion):
        subject = f"Nuevo Ticket de Soporte #{ticket_id}"
        body = f"""
        Se ha creado un nuevo ticket de soporte:

        ID: {ticket_id}
        Fecha: {fecha}
        Hora: {hora}
        Prioridad: {prioridad}
        Estado: {estado}
        Descripción: {descripcion}

        Por favor, atender a la brevedad posible.
        """
        
        try:
            self.email_sender.send_email("josegarjagt@gmail.com", subject, body)
            st.success("Correo de notificación enviado a soporte.")
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
                    st.write(f"Ticket #{row['id']} - {row['fecha']} {row['hora']} - {row['prioridad']} - {row['estado']}")
                    st.write(f"Descripción: {row['descripcion']}")
                with col2:
                    if st.button(f"Cerrar Ticket #{row['id']}"):
                        self.db.cerrar_ticket(row['id'])
                        st.success(f"Ticket #{row['id']} cerrado con éxito")
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