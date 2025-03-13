const MAX_RETRIES = 3;
const INITIAL_RETRY_DELAY = 1000; // 1 segundo

async function cargarDatosConReintento(spreadsheetId) {
  let intentos = 0;
  
  while (intentos < MAX_RETRIES) {
    try {
      // Intenta cargar los datos
      const response = await sheets.spreadsheets.values.get({
        spreadsheetId: spreadsheetId,
        range: 'A1:Z', // Ajusta el rango según tus necesidades
      });
      
      return response.data.values;
      
    } catch (error) {
      intentos++;
      
      if (error.code === 429) {
        console.log(`Límite de cuota excedido. Intento ${intentos} de ${MAX_RETRIES}`);
        
        // Calcula el tiempo de espera exponencial
        const tiempoEspera = INITIAL_RETRY_DELAY * Math.pow(2, intentos - 1);
        
        // Agrega algo de aleatoriedad para evitar que múltiples clientes reinicien al mismo tiempo
        const jitter = Math.random() * 1000;
        
        console.log(`Esperando ${tiempoEspera + jitter}ms antes de reintentar...`);
        
        // Espera antes de reintentar
        await new Promise(resolve => setTimeout(resolve, tiempoEspera + jitter));
        
        continue;
      }
      
      // Si es otro tipo de error, lo lanzamos inmediatamente
      throw error;
    }
  }
  
  // Si llegamos aquí, significa que agotamos todos los reintentos
  throw new Error(`No se pudieron cargar los datos después de ${MAX_RETRIES} intentos`);
}

// Función principal que utiliza el manejo de errores
async function obtenerDatosReservas() {
  try {
    const SPREADSHEET_ID = 'ID-DE-TU-SPREADSHEET-GESTION-RESERVAS-CLD';
    const datos = await cargarDatosConReintento(SPREADSHEET_ID);
    
    // Procesa los datos aquí
    return datos;
    
  } catch (error) {
    console.error('Error al procesar datos de reservas:', error);
    
    // Aquí puedes implementar una lógica específica según el tipo de error
    if (error.code === 429) {
      // Podrías mostrar un mensaje al usuario
      throw new Error('El servicio está experimentando alta demanda. Por favor, intenta más tarde.');
    }
    
    throw error;
  }
}

// Implementación de caché para reducir llamadas a la API
const cache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutos

async function obtenerDatosConCache() {
  const cacheKey = 'reservas-data';
  const cachedData = cache.get(cacheKey);
  
  if (cachedData && (Date.now() - cachedData.timestamp) < CACHE_TTL) {
    return cachedData.data;
  }
  
  const datos = await obtenerDatosReservas();
  cache.set(cacheKey, {
    data: datos,
    timestamp: Date.now()
  });
  
  return datos;
}
