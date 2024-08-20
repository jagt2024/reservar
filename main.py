import streamlit as st
from streamlit_option_menu import option_menu
import numpy as np
from inicio import Inicio
from crear_reserva import CrearReserva
from modificar_reserva import ModificarReserva
from eliminar_reserva import EliminarReserva
from servicios import Servicios
from informacion import Informacion
from generar_excel import GenerarExcel
from consulta_google_drive_excel import ConsultarAgenda
import datetime as dt
from openpyxl import load_workbook

datos_book = load_workbook("archivos/parametros.xlsx", read_only=False)

def dataBook(hoja):
    ws1 = datos_book[hoja]

    data = []
    for row in range(1,ws1.max_row):
      _row=[]
      for col in ws1.iter_cols(1,ws1.max_column):
        _row.append(col[row].value)   
      data.append(_row)
      #print(f'data {data}')
    return data

fecha_hasta = int('20241130')
#print(f'fecha hasta: {fecha_hasta}')

fecha = dt.datetime.now()
fecha_hoy = int(fecha.strftime("%Y%m%d"))
#print(f'fecha_hoy: {fecha_hoy}')

def dif_dias(dias):
  fecha = dt.datetime.now()
  hoy = dt.datetime(fecha.year, fecha.month, fecha.day)
  #fecha_hasta = dt.datetime(fecha_hasta.year, fecha_hasta.month, fecha_hasta.day)
  parsed_time = dt.datetime(fecha.year, fecha.month, fecha.day)
  new_time = (parsed_time + dt.timedelta(days=dias))
  old_time = (parsed_time - dt.timedelta(days=dias))
  tot_dias = new_time - old_time
  delta = tot_dias
   
  #print(delta.days)
  return hoy, new_time, old_time, delta.days

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
page_icon= "assets/barberia.png" 
title="Resevas"
layout = 'centered'

st.set_page_config(page_title=page_title, page_icon=page_icon,layout=layout)

class Model:
  
  menuTitle = "Reserve y Agende en Linea"
  option1 = 'Inicio'
  option2 = 'Crear Reserva'
  option3 = 'Modificar Reserva'
  option4 = 'Eliminar Reserva'
  option5 = 'Nuestros Servicios'
  option6 = 'Mas Informacion'
  option7 = 'Generar Archivos'
  option8 = 'Consultar Agenda'
    
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
                         [model.option1, model.option2,model.option3,model.option4,model.option5,model.option6,model.option7,model.option8],
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
                       #orientation='horizontal')
                       
      with st.sidebar:
        st.markdown("---")
        st.text("Version: 0.0.1")
        st.text("Ano: 2024")
        st.text("Autor: JAGT")
        st.markdown("---")
    
      if sw_persona == ['True']:

        st.title('***AGENDA PERSONAL***')

        if app == model.option1:
          Inicio().view(Inicio.Model())
        if app == model.option2:
          CrearReserva().view(CrearReserva.Model())
        if app == model.option3:
          ModificarReserva().view(ModificarReserva.Model())
        if app == model.option4:
          EliminarReserva().view(EliminarReserva.Model())
        if app == model.option5:
          Servicios().view(Servicios.Model())
        if app == model.option6:
          Informacion().view(Informacion.Model())
        if app == model.option7:
          GenerarExcel().view(GenerarExcel.Model())
        if app == model.option8:
          ConsultarAgenda().view(ConsultarAgenda.Model())
  
    except SystemError as err:
      raise Exception(f'A ocurrido un error en main.py: {err}')
          
  view(Model())