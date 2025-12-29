import google.generativeai as genai

from google.generativeai.types import FunctionDeclaration, Tool

# 1. Definimos las herramientas (El "Menú" para la IA)
tap_tool = {
    "function_declarations": [
        {
            "name": "tap_screen",
            "description": "Toca una coordenada específica en la pantalla del dispositivo móvil.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "Coordenada X horizontal"},
                    "y": {"type": "integer", "description": "Coordenada Y vertical"}
                },
                "required": ["x", "y"]
            }
        },
        {
            "name": "type_text",
            "description": "Escribe texto en el campo seleccionado actualmente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "El texto a escribir"}
                },
                "required": ["text"]
            }
        },
        # Aquí agregaremos la joya de la corona: get_ui_hierarchy
        {
            "name": "scan_screen",
            "description": "Obtiene la estructura de la pantalla (botones, textos) para saber dónde hacer click.",
            "parameters": {
                "type": "object",
                "properties": {}, # No requiere argumentos
            }
        }
    ]
}

# 2. Inicializamos el modelo con las herramientas
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash', # O Pro, es más barato y rápido el flash
    tools=[tap_tool] 
)

chat = model.start_chat(enable_automatic_function_calling=False) # Lo haremos manual para controlar el WebSocket

# 3. Función para procesar mensajes del usuario (desde AsyncControl)
async def process_user_message(user_message, connection_manager):
    response = chat.send_message(user_message)
    
    # ¿Gemini quiere usar una herramienta?
    if response.candidates[0].content.parts[0].function_call:
        fc = response.candidates[0].content.parts[0].function_call
        function_name = fc.name
        args = fc.args
        
        print(f"🤖 Gemini quiere ejecutar: {function_name} con {args}")
        
        # AQUÍ CONECTAMOS CON TU WEBSOCKET MANAGER
        if function_name == "tap_screen":
            # Construimos el JSON para TypusControlMini
            cmd_payload = {
                "type": "command", 
                "command": "tap", 
                "x": args["x"], 
                "y": args["y"]
            }
            # Enviamos al móvil
            await connection_manager.send_command_to_streamer(..., cmd_payload)
            
            # Le confirmamos a la IA que se hizo
            return "Acción ejecutada exitosamente."
            
        elif function_name == "scan_screen":
            # Pides el JSON al móvil, esperas respuesta y se la das a la IA
            # (Esto requerirá un pequeño ajuste para esperar la respuesta del WS)
            pass

    return response.text