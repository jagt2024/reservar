import qrcode
#import pandas as pd
from openpyxl import load_workbook

datos_book = load_workbook("../archivos/parametros_abogados.xlsx", read_only=False)

#data = pd.read_csv('BASE.csv')
#print(data.head())

def dataBookServicio(hoja):
    ws1 = datos_book[hoja]
    data = []
    for row in ws1.iter_rows(min_row=2, min_col=0):
      resultado = [col.value for col in row]
      data.append(resultado[0:4])
      #print(f'data {data}')
    return data
  
encargado = dataBookServicio("encargado")
cedula = encargado[0][3]
#print(f'Encargado {encargado}, cedula: {cedula}')

for i in range(len(encargado)):
  cod_proveedor = encargado[i][3]
  nombre_proveedor = encargado[i][0]
  telefono = encargado[i][2]
    
  img = qrcode.make(cod_proveedor)
  img.save(f"img/{nombre_proveedor}.png")