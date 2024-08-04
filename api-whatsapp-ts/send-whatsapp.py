import requests
import time

def sendMessage(numero, mensaje):
  url = 'http://localhost:3001/lead'
  
  numero = "573205511091"
  mensaje = "Enviado desde el programa .py"
  
  data = {
    "message": mensaje,
    "phone": numero 
  }
  headers = {
    'Content-Type': 'application/json'
  }
  print(data)
  response = requests.post(url, json=data, headers=headers)
  time.sleep(10)
  return response

sendMessage("numero", "mensaje")