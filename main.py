import streamlit as st
from streamlit_option_menu import option_menu
import numpy as np
from inicio import Inicio
from inicio_emp import InicioEmp
from crear_reserva import CrearReserva
from crear_reserva_emp import CrearReservaEmp
from modificar_reserva import ModificarReserva
from modificar_reserva_emp import ModificarReservaEmp
from eliminar_reserva import EliminarReserva
from eliminar_reserva_emp import EliminarReservaEmp
from servicios import Servicios
from servicios_emp import ServiciosEmp
from informacion import Informacion
from informacion_emp import InformacionEmp
from generar_excel import GenerarExcel
from generar_excel_emp import GenerarExcelEmp
import datetime as dt
from openpyxl import load_workbook

datos_book = load_workbook("archivos/parametros.xlsx", read_only=False)
datos_book_emp = load_workbook("archivos/parametros_empresa.xlsx", read_only=False)

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

def dataBook_emp(hoja):
    ws1 = datos_book_emp[hoja]
    data = []
    for row in range(1,ws1.max_row):
      _row=[]
      for col in ws1.iter_cols(1,ws1.max_column):
        _row.append(col[row].value)
      data.append(_row)
      #print(f'data {data}')
    return data

def dif_dias(dias):
  fecha = dt.datetime.now()
  parsed_time = dt.datetime(fecha.year, fecha.month, fecha.day)
  new_time = (parsed_time + dt.timedelta(days=dias))
  delta = parsed_time - new_time
    
  #print(delta.days)
  return new_time, delta.days

dia, delta = dif_dias(1)
fechafin = int(dia.strftime("%Y%m%d"))
#print(f'dia: {dia}, delta: {delta}, fechafin: {fechafin}')

persona = dataBook("sw")
result_per = np.setdiff1d(persona,'')

empresa = dataBook_emp("sw")
result_emp = np.setdiff1d(empresa,'')
#print(f'sw_empresa {result_emp}')

hoy = dt.datetime.now()
fechoy = int(hoy.strftime("%Y%m%d"))

sw_empresa = result_emp
sw_persona = result_per

#ws = result_emp
   #ws = result_emp["A2"].value
#print(ws)
#if sw_empresa == ["False"]:
#    hojaemp.value="True"
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
  
def view(model):
  try:
  
    #st.title('***ORGANIZACION O PERSONA***')
    #st.subheader('Genere sus Reservas en Linea y Recibira confirmacion a su correo')
  
    with st.sidebar:
    
      app = option_menu(model.menuTitle,
                        [model.option1, model.option2,model.option3,model.option4,model.option5,model.option6,model.option7],
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
                          "nav-lik":{"color":"white","font-size":"20px","text-aling":"left","margin":"0px"},
                          "nav-lik-selected":{"backgroud-color":"#02ab21"},})
                       #orientation='horizontal')
                       
    with st.sidebar:
      st.markdown("---")
      st.text("Version: 0.0.1")
      st.text("Ano: 2024")
      st.markdown("---")
    
    if fechafin < fechoy:
      sw_empresa == ['False']

    if sw_empresa == ['True']:
      
      st.title('***BARBERIA STYLOS***')
      
      if app == model.option1:
        InicioEmp().view(InicioEmp.Model())
      if app == model.option2:
        CrearReservaEmp().view(CrearReservaEmp.Model())
      if app == model.option3:
        ModificarReservaEmp().view(ModificarReservaEmp.Model())
      if app == model.option4:
        EliminarReservaEmp().view(EliminarReservaEmp.Model())
      if app == model.option5:
        ServiciosEmp().view(ServiciosEmp.Model())
      if app == model.option6:
        InformacionEmp().view(InformacionEmp.Model())
      if app == model.option7:
        GenerarExcelEmp().view(GenerarExcelEmp.Model())
    
    if fechafin < fechoy:
      sw_persona == ['False']
      
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
  
  except SystemError as err:
   raise Exception(f'A ocurrido un error en main.py: {err}')
          
view(Model())