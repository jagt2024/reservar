def actualizar_reserva(conn, nombre, fecha, hora, servicio, nuevos_datos):
    """
    Actualiza una reserva existente buscando por nombre, fecha, hora y servicio.
    
    Args:
        conn: Conexión a la base de datos
        nombre: Nombre del cliente para buscar
        fecha: Fecha de la reserva para buscar
        hora: Hora de la reserva para buscar
        servicio: Servicio de la reserva para buscar
        nuevos_datos: Diccionario con los campos a actualizar
        
    Returns:
        int: Número de filas actualizadas
        None: Si ocurre un error
    """
    from sqlite3 import Error
    
    try:
        # Construir la consulta SQL dinámicamente basada en los campos a actualizar
        set_clauses = []
        params = []
        
        # Mapeo de campos permitidos para actualizar
        campos_permitidos = {
            'nombre': 'nombre',
            'email': 'email',
            'fecha': 'fecha',
            'hora': 'hora',
            'servicio': 'servicio',
            'precio': 'precio',
            'encargado': 'encargado',
            'email_encargado': 'email_encargado',
            'zona': 'zona',
            'direccion': 'direccion',
            'notas': 'notas',
            'uid': 'uid',
            'whatsapp': 'whatsapp',
            'telefono': 'telefono',
            'whatsapp_web': 'whatsapp_web'
        }
        
        # Construir las cláusulas SET y parámetros
        for key, value in nuevos_datos.items():
            if key in campos_permitidos:
                set_clauses.append(f"{campos_permitidos[key]}=?")
                params.append(value)
        
        # Si no hay campos para actualizar, retornar
        if not set_clauses:
            print("No se proporcionaron campos válidos para actualizar")
            return 0
        
        # Construir la consulta SQL completa
        sql = f'''UPDATE reservas 
                SET {', '.join(set_clauses)}
                WHERE nombre=? 
                AND fecha=? 
                AND hora=? 
                AND servicio=?'''
        
        # Agregar los parámetros de búsqueda
        params.extend([nombre, fecha, hora, servicio])
        
        # Ejecutar la consulta
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        
        # Retornar el número de filas afectadas
        rows_affected = cursor.rowcount
        if rows_affected == 0:
            print("No se encontró ninguna reserva que coincida con los criterios de búsqueda")
        else:
            print(f"Se actualizó exitosamente la reserva")
        return rows_affected
    
    except Error as e:
        print(f"Error actualizando reserva: {e}")
        return None

# Ejemplo de uso de la función:
"""
# Parámetros de búsqueda
nombre_buscar = "Juan Pérez"
fecha_buscar = "2024-10-27"
hora_buscar = "15:30"
servicio_buscar = "Corte de cabello"

# Nuevos datos a actualizar (solo los campos que quieres cambiar)
nuevos_datos = {
    'email': 'nuevo@email.com',
    'precio': 40.00,
    'notas': 'Actualización de datos',
    'telefono': '9876543210'
}

# Llamar a la función
resultado = actualizar_reserva(
    conn,
    nombre_buscar,
    fecha_buscar,
    hora_buscar,
    servicio_buscar,
    nuevos_datos
)

# Verificar el resultado
if resultado:
    print(f"Se actualizaron {resultado} registros")
else:
    print("No se pudo realizar la actualización")
"""
