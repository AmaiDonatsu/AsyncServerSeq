Estoy refactorizando mi servidor AsyncServerSeq. Actualmente tengo un ConnectionManager en routes/ws_endpoint.py que envía mensajes JSON a clientes WebSocket (dispositivos Android).

Necesito crear un nuevo servicio llamado services/ai_agent.py que haga lo siguiente:

Inicialice el modelo gemini-2.5-flash con herramientas (Function Calling).

Defina herramientas (Tools) que coincidan EXACTAMENTE con los comandos que espera mi app Android (tap, type, swipe, home, back).

Requisito Crítico: Cuando el modelo decida usar una herramienta (ej: 'tap_screen'), la función en Python NO debe ejecutar nada localmente. Debe construir un diccionario JSON con este formato exacto y devolverlo: { "type": "command", "command": "tap", "x": ..., "y": ... }

Las herramientas a definir son:

tap_screen(x, y) -> Mapea a command: 'tap'

type_text(text) -> Mapea a command: 'inputText'

press_back() -> Mapea a command: 'back'

press_home() -> Mapea a command: 'home'

get_screen_tree() -> Mapea a command: 'getUI'

Por favor, genera el código para services/ai_agent.py incluyendo la configuración del modelo y la definición de estas herramientas."