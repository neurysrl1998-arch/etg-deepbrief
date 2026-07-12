# 📰 ETG DEEPBRIEF v3.2 — El Periódico del Trading en Vivo

## 🆕 Novedades v3.2 — "Analista IA"

Requiere conectar tu **modelo Llama local** (llama.cpp, LM Studio, etc. con API estilo OpenAI).
En ⚙️ → sección "INTELIGENCIA ARTIFICIAL" escribe la URL de tu servidor (ej. `http://127.0.0.1:8080`) y Guardar.
Corre 100% en tu GPU — nada sale de tu PC. Sin conectar, estas funciones quedan ocultas/en espera.

| Módulo | Detalle |
|---|---|
| 🧠 Editorial IA | La portada abre con un briefing de 2 párrafos redactado por tu IA a partir de los titulares del momento: panorama, sesgo risk-on/off, riesgos clave y qué vigilar. Se regenera solo cada ~12 min; botón ↻ para forzarlo. |
| 💬 Pregúntale al mercado | Botón 💬 en la barra: chat con tu analista IA que usa las noticias recientes como contexto. Pregúntale "¿qué significa esto para el NQ?" y responde en segundos. Sugerencias rápidas incluidas. |
| 📊 VXN Nasdaq-100 | El panel de volatilidad ahora usa VXN (CBOE Nasdaq-100) en vez del VIX — el índice correcto para trading de NQ. |
| 🎯 Barra superior | Rediseñada en 3 zonas para que nunca se compriman los controles. |

> ⚠️ El editorial y el chat son **informativos**, no consejo financiero personalizado.


## 🆕 Novedades v3.0 — "El Analista"

| Módulo | Detalle |
|---|---|
| 📸 Sello de precio | Cada noticia CRÍTICA/ALTA guarda una foto del mercado (NQ, ES, Oro, Petróleo, VIX) en ese instante. Después la tarjeta muestra "Desde esta noticia: CL +3.2% · NQ −1.1%" — ves qué noticias mueven el mercado de verdad. |
| 🔗 Confirmación multi-fuente | El agente agrupa titulares similares: "✅ CONFIRMADO ×18" = 18 medios reportando lo mismo. 1 fuente = rumor; muchas = evento real. Así validan los desks institucionales. |
| 🧠 Analista | Cada noticia importante recibe análisis automático: sesgo (RISK-ON/OFF), instrumentos ▲/▼ y consejo operativo. Opcional: conecta tu Llama 8B local poniendo la URL del servidor llama.cpp en `settings.json` → `"llama_url": "http://127.0.0.1:8080"` y el análisis pasa a ser IA generativa real. |
| 📉 Sparklines | Mini-gráfico de la sesión dentro de cada tarjeta de futuros (en fin de semana muestra los últimos días). |
| ⚡ Velocímetro | Si NQ/ES/Oro/Petróleo se mueve 3× más rápido de lo normal en 5 min, te salta aviso — muchas veces el precio se mueve ANTES de la noticia. |
| 🌅 Informe Pre-Apertura | Botón 🌅 en la cabecera: dónde quedó el mercado el viernes, todo lo que pasó el fin de semana (con análisis), tensión y próximos eventos rojos. Se abre SOLO los domingos 17:30 NY, antes de Globex. |
| ⚔️ Modo Guerra automático | Tensión ≥ 70 → la app entera se pone en tema Rojo Guerra, insignia ⚔️ y alertas aceleradas a 15 s. Baja la tensión → vuelve solo a tu tema. Desactivable en ⚙️. |
| 🖥️ Modo Cinta | Ventana delgada (futuros + VIX + ticker + alerta crítica) para el 2º monitor encima de NinjaTrader. Ábrela desde ⚙️ o desde el icono de la bandeja. |
| 🪟 Vigilancia 24/7 | Icono en la bandeja del sistema (junto al reloj). Cierra la ventana y el motor SIGUE investigando: si llega un CRÍTICO te salta una notificación nativa de Windows. Clic en el icono → reabrir panel. "Salir del todo" para apagar el motor. |


Tu agente investigador personal. Nada habla: investiga solo, puntúa el impacto
de cada noticia y te lo pone todo en una pantalla estilo periódico.

## 🚀 Cómo abrirlo

- **Opción 1 (recomendada):** doble clic a `dist\ETG DeepBrief.exe`
- **Opción 2:** doble clic a `ETG DeepBrief.bat` (usa Python directamente)

Se abre solo en una ventana de Edge sin barras (modo app). Para cerrar la app
del todo, cierra la ventana y termina `pythonw.exe` / `ETG DeepBrief.exe`
desde el Administrador de tareas si quieres detener el motor.

## 🧠 Qué hace el agente

| Módulo | Detalle |
|---|---|
| 📡 15 fuentes | Google News (Irán, Trump, Fed, futuros, petróleo), Al Jazeera, BBC, CNBC, MarketWatch, ZeroHedge, FXStreet, Reddit |
| 🎯 Motor de impacto | Cada titular se puntúa: CRÍTICO / ALTO / MEDIO / BAJO según palabras clave geopolíticas y de mercado |
| 🚨 Alerta crítica | Si Irán ataca (o algo CRÍTICO ocurre), banner rojo parpadeante + campana opcional 🔔 |
| ☢️ Tensión geopolítica | Termómetro 0-100 calculado con las noticias de las últimas 3 horas |
| 📈 Futuros en vivo | NQ, ES, YM, Oro, Petróleo, Plata, VIX, DXY, 10Y, BTC, EUR/USD cada 20 s |
| 📅 Calendario económico | Eventos del día hora NY + cuenta regresiva al próximo evento rojo (fin de semana muestra el lunes) |
| 😱 Fear & Greed | Índice CNN en vivo |
| 📰 Portada | Lo más relevante de las últimas 14 h, agrupado por tema — tu "mientras dormías" |
| 👁️ Vigilancia personal | Agrega palabras clave (ej. "Powell", "OPEC") y el agente las rastrea en la prensa mundial |
| 🕐 Sesión NY | Reloj NY + estado del mercado (pre-market / abierto / Globex) con cuenta regresiva |
| 🌐 Idioma ES/EN | Botón en la cabecera: traduce TODOS los titulares al español automáticamente (portada, stream, ticker y alertas). Los primeros tardan ~15 s; el resto se completa solo en ~1 min y las noticias nuevas llegan ya traducidas. Recuerda tu preferencia. |

## 🆕 Novedades v2.0

| Módulo | Detalle |
|---|---|
| 🧲 Paneles movibles | Arrastra cualquier panel desde el asa ⠿ de su título y suéltalo en la columna izquierda o derecha, en el orden que quieras. La app recuerda TU distribución. Restablecer desde ⚙️. |
| ⚙️ Configuración | Botón en la cabecera: 5 temas de colores (ETG Oro, Terminal Azul, Matrix Verde, Marfil Claro, Rojo Guerra) + interruptores de alertas. |
| 🔥 Noticias calientes | Titulares CRÍTICOS/ALTOS de los últimos 30 min brillan con animación dorada y etiqueta 🔥 CALIENTE en el stream. |
| 🪟 Ventana emergente | Cuando llega una noticia caliente NUEVA, salta una tarjeta deslizante (arriba a la derecha) con el titular — clic para leerla, ✕ para cerrarla. Desactivable en ⚙️. |
| 🚨 Animación ÚLTIMA HORA | Si llega algo CRÍTICO: banner estilo TV desciende al centro con brillo barrido + viñeta roja pulsante en toda la pantalla + doble campana (si el sonido está activo). Se cierra solo en 12 s o con clic. |
| 🌪️ Panel VIX / Volatilidad | VIX en vivo con estado BAJA/NORMAL/ELEVADA/EXTREMA, medidor animado y consejo operativo para futuros. Si VIX ≥ 25 o sube +10%, aparece el aviso 🌪️ ALTA VOLATILIDAD en la cabecera + notificación. |
| 👁️ Vigilante global | Las alertas ahora vigilan TODAS las categorías aunque tengas un filtro activo (antes, si estabas en GEO, un crítico de FED no te avisaba). |

## ⏱️ Frecuencias
- Noticias: cada **45 s** · Futuros: cada **20 s** · Calendario/F&G: cada 5 min

## 📌 Notas honestas
- Las fuentes son públicas y gratis: la velocidad real es de segundos a pocos
  minutos tras publicarse en los medios grandes (no es un terminal Bloomberg,
  pero es lo más rápido posible sin pagar wires).
- ForexFactory publica la semana siguiente el domingo; el sábado el calendario
  puede verse vacío.
- Todo corre 100 % local en tu PC (puerto 127.0.0.1:8765). Nada se sube a nube.
