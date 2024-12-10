import streamlit as st
from streamlit_option_menu import option_menu
import numpy as np
from inicio_abo import Inicio
from crear_reserva_abo import CrearReserva
from modificar_reserva_abo import ModificarReservaAbo
from eliminar_reserva_abo import EliminarReserva
from servicios_abo import Servicios
from informacion_abo import Informacion
from generar_excel_abo import GenerarExcel
from generaQR.generar_qr_abo import GenerarQr
from consulta_st_excel import ConsultarAgenda
from descargar_agenda_abo import download_and_process_data
from user_management import user_management_system, logout
from buscar_info import streamlit_app
from facturacion_servicios_abo import generar_factura
from estadisticas_reservas_abo import main_reservas_abo
from estadisticas_facturacion_abo import main_factura
from whatsapp_sender_abo import whatsapp_sender
from ticket_support_app import soporte
import datetime as dt
from openpyxl import load_workbook
from calendar import month_name
from datetime import date
import os
import datetime
import time
import pytz
import toml
from PIL import Image
import sys
import logging

st.cache_data.clear()
st.cache_resource.clear()

def clear_session_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
 
def global_exception_handler(exc_type, exc_value, exc_traceback):
    st.error(f"Error no manejado: {exc_type.__name__}: {exc_value}")
    logging.error("Error no manejado", exc_info=(exc_type, exc_value, exc_traceback))

logging.basicConfig(level=logging.DEBUG, filename='main_abo.log', filemode='w',
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# En diferentes partes de tu código:
#logging.debug('Entrando en función X')

# Cargar configuraciones desde config.toml
with open("./.streamlit/config.toml", "r") as f:
    config = toml.load(f)

os.environ["REQUESTS_CONNECT_TIMEOUT"] = "5"
os.environ["REQUESTS_READ_TIMEOUT"] = "5"

logo = Image.open("./assets/logoJAGT.ico")

datos_book = load_workbook("archivos/parametros_abogados.xlsx", read_only=False)

def dataBook(hoja):
    ws1 = datos_book[hoja]

    data = []
    for row in range(1,ws1.max_row):
      _row=[]
      for col in ws1.iter_cols(1,ws1.max_column):
        _row.append(col[row].value)   
      data.append(_row[0])
      #print(f'data {data}')
    return data

fecha_hasta = int('20250228')
#print(f'fecha hasta: {fecha_hasta}')

fecha = dt.datetime.now()
fecha_hoy = int(fecha.strftime("%Y%m%d"))
#print(f'fecha_hoy: {fecha_hoy}')

#def dif_dias(dias):
#  fecha = dt.datetime.now()
#  hoy = dt.datetime(fecha.year, fecha.month, fecha.day)
  #fecha_hasta = dt.datetime(fecha_hasta.year, fecha_hasta.month, fecha_hasta.day)
#  parsed_time = dt.datetime(fecha.year, fecha.month, fecha.day)
#  new_time = (parsed_time + dt.timedelta(days=dias))
#  old_time = (parsed_time - dt.timedelta(days=dias))
#  tot_dias = new_time - old_time
#  delta = tot_dias
   
  #print(delta.days)
#  return hoy, new_time, old_time, delta.days

#hoy, dia, olddia, delta = dif_dias(1)

#fechafin = int(dia.strftime("%Y%m%d"))
#print(f'hoy: {hoy}, dia: {dia}, difdias: {olddia}, delta: {delta}, fechafin: {fechafin}')

persona = dataBook("sw")
result_per = np.setdiff1d(persona,'')

sw_persona = result_per

#ws = result_emp
   #ws = result_emp["A2"].value
#print(ws)
#if sw_empresa == ["False"]:
    #empresa.cell(column=1, row=2).value = ["True"])
#    sw_empresa = ["True"]
#    print(sw_empresa)
  
page_title = 'Agenda Actividad' 
page_icon= "assets/plantilla-logo-bufete-abogados.avif" 
title="Resevas"
layout = 'centered'

st.set_page_config(page_title=page_title, page_icon=page_icon,layout=layout)

class Model:
  
  menuTitle = "Reserve y Agende en Linea"
  option1  = 'Inicio'
  #option2  = 'Crear Reserva'
  option10 = 'Descargar Agenda'
  option9  = 'Consultar Agenda'
  #option3  = 'Modificar Reserva'
  #option4  = 'Eliminar Reserva'
  option5  = 'Nuestros Servicios'
  option6  = 'Mas Informacion'
  option7  = 'Generar Archivos'
  option8  = 'Generar Codigo QR'
  option11 = 'Buscar Informacion'
  option15 = 'Enviar Whatsapp'
  option12 = 'Facturacion'
  option13 = 'Estadisticas de Resservas'
  option14 = 'Estadisticas de Facturacion'
  option16 = 'Soporte - PQRS'
  
  #def __init__(self):
  #  self.apps=[]
    
  def add_app(self,title, function):
      self.apps.append({
         "title":title,
         "function":function
       })
      
  def css_load(css_file):
    
    #file_path = r"C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas/style/main.css"
    #print(file_path)

    #try:
    #  if os.path.exists(file_path):
    #    pass
        #os.chmod(file_path, 0o666)
        #print("File permissions modified successfully!")
    #  else:
    #    print("File not found:", file_path)
    #except PermissionError:
    #  print("Permission denied: You don't have the necessary permissions to change the permissions of this file.")
    
    try:
      with open(css_file, "r") as file:
        st.markdown(f"<style>{file.read()}</style>",unsafe_allow_html=True)
    except IOError  as e:
      if "not readable" in str(e):
        print("Error no readable check mode")
      else:
        print(f"IOError {e}")
      
  css_load(r"style/main.css")

if fecha_hasta < fecha_hoy:
  
   sw_persona == ['False']
      
   st.warning('Ha caducado el tiempo autorizado para su uso favor comuniquese con el administrador')

else:  

  def view(model):
    try:
  
      with st.sidebar:
    
        app = option_menu(model.menuTitle,
                         [model.option1, model.option10, model.option9, model.option5,model.option6,model.option7, model.option8, model.option11, model.option15, model.option12, model.option13, model.option14, model.option16],
                         icons=['bi bi-app-indicator',
                                'bi bi-calendar2-date', 
                                'bi bi-calendar2-date',
                                'bi bi-calendar2-date',
                                'bi bi-award',
                                'bi bi-clipboard-minus-fill'
                               ],
                         default_index=0,
                         styles= {
                           "container":{ "reservas": "5!important",
                           "background-color":'#acbee9'},
                           "icon":{"color":"white","font-size":"23px"},
                           "nav-lik":{"color":"white","font-size":"20px","text-aling":"left", "margin":"0px"},
                           "nav-lik-selected":{"backgroud-color":"#02ab21"},})
                       #orientatio'horizontal')

      st.markdown(f"""
      <style>
            @import url('https://fonts.googleapis.com/css2?family={config['fonts']['clock_font']}:wght@400;500&display=swap');
            .clock {{
              font-family: '{config['fonts']['clock_font']}', sans-serif;
              font-size: {config['font_sizes']['clock_font_size']};
              color: {config['colors']['clock_color']};
              text-shadow: 0 0 10px rgba(255,255,0,0.7);
              margin-top: {config['layout']['top_margin']};
              margin-bottom: {config['layout']['bottom_margin']};
            }}
            .calendar {{
              font-family: '{config['fonts']['calendar_font']}', sans-serif;
              font-size: {config['font_sizes']['calendar_font_size']};
              color: {config['colors']['calendar_color']};
              margin-top: {config['layout']['top_margin']};
              margin-bottom: {config['layout']['bottom_margin']};
            }}
      </style>
      """, unsafe_allow_html=True)

      # Crear columnas para el diseño
      col1, col2, col3, col4 = st.columns(4)

      # Columna 1: Reloj Digital
      with col1:
          #st.header("Reloj Digital")
          clock_placeholder = st.empty()
                
      with col2:
          st.image(logo, width=150)  # Ajusta el ancho según sea necesario
        
        # Columna 2: Calendario
      with col3:
          #st.header("Calendario")
          calendar_placeholder = st.empty()
          
      with col4:

         with st.form(key='myform4',clear_on_submit=True):
            limpiar = st.form_submit_button("Limpiar Opcion")
            if limpiar:
              #st.submit_button("Limpiar Opcion")
              clear_session_state()
              st.rerun()
        
      # Crear los tabs con los estilos personalizados
               
      tabs = st.tabs(["Inicio", "Crear Reserva", "Modificar Reserva", "Eliminar Reserva", "Informacion", "Servicios" ])
    
      with tabs[0]:
         Inicio().view(Inicio.Model())
             
      with tabs[1]:
         CrearReserva().view(CrearReserva.Model())
    
      with tabs[2]:
         ModificarReservaAbo().view(ModificarReservaAbo.Model())
    
      with tabs[3]:
          EliminarReserva().view(EliminarReserva.Model())
      
      with tabs[4]:
          Informacion().view(Informacion.Model())
          
      with tabs[5]:
          Servicios().view(Servicios.Model())
          
      def update_clock_and_calendar():
         while True:
              now = datetime.datetime.now(pytz.timezone('America/Bogota'))
              clock_placeholder.markdown(f'<p class="clock">Hora: {now.strftime("%H:%M:%S")}</p>', unsafe_allow_html=True)

              today = date.today()
              meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
              mes_es = meses_es[today.month - 1]
              dias_es = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
              dia_es = dias_es[today.weekday()]
        
              calendar_placeholder.markdown(f'<p class="calendar">Día: {dia_es.capitalize()} {today.day} de {mes_es} de {today.year}<br></p>', unsafe_allow_html=True)
        
              time.sleep(5)
              #st.experimental_rerun()   

      with st.sidebar:
        st.markdown("---")
        st.text("Version: 0.0.1")
        st.text("Ano: 2024")
        st.text("Autor: JAGT")
        st.markdown("---")

        st.markdown("""
        <script>
          window.onerror = function(message, source, lineno, colno, error) {
          fetch('/log_error', {
          method: 'POST',
          headers: {'Content-Type': 'main_abo/json'},
          body: JSON.stringify({message, source, lineno, colno, error: error.stack})
            });
          };
        </script>
        """, unsafe_allow_html=True)
   
      if sw_persona == ['True']:

        #st.title('***BUFETE ABOGADOS***')

        if app == model.option1:
          Inicio().view(Inicio.Model())
        #if app == model.option2:
        #  CrearReserva().view(CrearReserva.Model())
        #if app == model.option3:
        #  ModificarReservaAbo().view(ModificarReservaAbo.Model())
        #if app == model.option4:
        #  EliminarReserva().view(EliminarReserva.Model())
        if app == model.option5:
          Servicios().view(Servicios.Model())
        if app == model.option6:
          Informacion().view(Informacion.Model())
        if app == model.option7:
          GenerarExcel().view(GenerarExcel.Model())
        if app == model.option8:
          GenerarQr().view(GenerarQr.Model())
        if app == model.option9:
           ConsultarAgenda().view(ConsultarAgenda.Model())
        if app == model.option10:
           #if user_management_system():
           download_and_process_data('./.streamlit/secrets.toml')
           #  logout()
        if app == model.option11:
           streamlit_app()
        if app == model.option12:

           generar_factura()
                            
        if app == model.option13:
           
           #if authenticate_user(): 
            
           main_reservas_abo()
                            
        if app == model.option14:
           
           #if authenticate_user():
          
           main_factura()
           
        if app == model.option15:
           
           #if authenticate_user(): 
           whatsapp_sender()
        
        if app == model.option16:
           soporte()
               
        #logging.info('Estado actual: %s', app)

    except SystemError as err:
      raise Exception(f'A ocurrido un error en main_abo.py: {err}')
    except Exception as e:
        st.error(f"Ocurrió un error en main_abo.py: {e}")
    # Iniciar la actualización del reloj y calendario
    
    update_clock_and_calendar()
    
    sys.excepthook = global_exception_handler
        
  view(Model())
