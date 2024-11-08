# app_launcher.py
import tkinter as tk
from tkinter import ttk
import webbrowser
from PIL import Image, ImageTk
import sys
import os

class AppLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("DP Launcher")
        
        # Obtener la ruta del directorio del ejecutable
        if getattr(sys, 'frozen', False):
            application_path = sys._MEIPASS
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        
        # Configurar el ícono de la ventana
        icon_path = os.path.join(application_path, "assets-dp/dp_andres.png")
        if os.path.exists(icon_path):
            self.root.iconphoto(False, tk.PhotoImage(file=icon_path))
        
        # Configurar el estilo
        style = ttk.Style()
        style.configure("Custom.TButton", padding=10)
        
        # Crear el frame principal
        main_frame = ttk.Frame(root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Cargar y redimensionar la imagen
        try:
            image = Image.open(icon_path)
            image = image.resize((64, 64), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(image)
            
            # Crear botón con imagen
            self.launch_button = ttk.Button(
                main_frame,
                image=self.photo,
                command=self.launch_app,
                style="Custom.TButton"
            )
            self.launch_button.grid(row=0, column=0, padx=5, pady=5)
            
            # Añadir texto debajo del ícono
            label = ttk.Label(main_frame, text="DP Reservas")
            label.grid(row=1, column=0, pady=(0, 10))
            
        except Exception as e:
            print(f"Error al cargar la imagen: {e}")
            # Crear botón de respaldo sin imagen
            self.launch_button = ttk.Button(
                main_frame,
                text="Abrir DP Reservas",
                command=self.launch_app,
                style="Custom.TButton"
            )
            self.launch_button.grid(row=0, column=0, padx=5, pady=5)
    
    def launch_app(self):
        webbrowser.open("https://reservar-dp.streamlit.app/")

def main():
    root = tk.Tk()
    root.resizable(False, False)  # Hacer la ventana no redimensionable
    app = AppLauncher(root)
    # Centrar la ventana
    root.eval('tk::PlaceWindow . center')
    root.mainloop()

if __name__ == "__main__":
    main()
