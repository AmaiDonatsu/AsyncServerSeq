"""
AI Agent Service - Gemini Function Calling for Android Device Control

Este servicio maneja la comunicación con Gemini 2.5 Flash para controlar
dispositivos Android a través de WebSocket. Las herramientas definidas
generan comandos JSON que se envían al dispositivo móvil.
"""

import os
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

load_dotenv()

# Configurar API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)


# ==========================================
# Definición de Herramientas (Tools)
# ==========================================

# Herramienta: tap_screen -> command: 'tap'
tap_screen_declaration = FunctionDeclaration(
    name="tap_screen",
    description="Toca una coordenada específica en la pantalla del dispositivo móvil. Usa esto para hacer click en botones, enlaces o cualquier elemento interactivo.",
    parameters={
        "type": "object",
        "properties": {
            "x": {
                "type": "integer",
                "description": "Coordenada X horizontal en píxeles"
            },
            "y": {
                "type": "integer",
                "description": "Coordenada Y vertical en píxeles"
            }
        },
        "required": ["x", "y"]
    }
)

# Herramienta: type_text -> command: 'inputText'
type_text_declaration = FunctionDeclaration(
    name="type_text",
    description="Escribe texto en el campo de entrada actualmente seleccionado. Usa esto después de hacer tap en un campo de texto.",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "El texto a escribir en el campo"
            }
        },
        "required": ["text"]
    }
)

# Herramienta: press_back -> command: 'back'
press_back_declaration = FunctionDeclaration(
    name="press_back",
    description="Presiona el botón de retroceso (back) del dispositivo Android. Útil para volver a la pantalla anterior o cerrar diálogos.",
    parameters={
        "type": "object",
        "properties": {}
    }
)

# Herramienta: press_home -> command: 'home'
press_home_declaration = FunctionDeclaration(
    name="press_home",
    description="Presiona el botón de inicio (home) del dispositivo Android. Lleva al usuario a la pantalla principal.",
    parameters={
        "type": "object",
        "properties": {}
    }
)

# Herramienta: get_screen_tree -> command: 'getUI'
get_screen_tree_declaration = FunctionDeclaration(
    name="get_screen_tree",
    description="Obtiene la estructura jerárquica de la interfaz de usuario actual (UI Tree). Usa esto para analizar qué elementos hay en pantalla, sus coordenadas y propiedades antes de interactuar.",
    parameters={
        "type": "object",
        "properties": {}
    }
)

# Crear el Tool con todas las declaraciones
android_control_tool = Tool(
    function_declarations=[
        tap_screen_declaration,
        type_text_declaration,
        press_back_declaration,
        press_home_declaration,
        get_screen_tree_declaration
    ]
)


# ==========================================
# Mapeo de Funciones a Comandos JSON
# ==========================================

def build_command_payload(function_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Construye el payload JSON para enviar al dispositivo Android
    basándose en la función llamada por Gemini.
    
    Args:
        function_name: Nombre de la función invocada por el modelo
        args: Argumentos de la función
    
    Returns:
        Dict con el comando JSON para el dispositivo, o None si la función no existe
    """
    
    command_map = {
        "tap_screen": lambda a: {
            "type": "command",
            "command": "tap",
            "x": a.get("x"),
            "y": a.get("y")
        },
        "type_text": lambda a: {
            "type": "command",
            "command": "inputText",
            "text": a.get("text")
        },
        "press_back": lambda a: {
            "type": "command",
            "command": "back"
        },
        "press_home": lambda a: {
            "type": "command",
            "command": "home"
        },
        "get_screen_tree": lambda a: {
            "type": "command",
            "command": "getUI"
        }
    }
    
    builder = command_map.get(function_name)
    if builder:
        return builder(args)
    return None


# ==========================================
# Clase AIAgent
# ==========================================

class AIAgent:
    """
    Agente de IA que procesa mensajes del usuario y genera comandos
    para controlar dispositivos Android.
    """
    
    def __init__(self, system_instruction: Optional[str] = None):
        """
        Inicializa el agente con el modelo Gemini.
        
        Args:
            system_instruction: Instrucciones del sistema para el modelo
        """
        default_instruction = """Eres un asistente que controla dispositivos Android remotamente.
        
Tu trabajo es:
1. Analizar la pantalla usando get_screen_tree cuando necesites saber qué hay en pantalla
2. Usar tap_screen para hacer click en elementos específicos
3. Usar type_text para escribir texto en campos de entrada
4. Usar press_back para volver atrás
5. Usar press_home para ir al inicio

Siempre analiza la pantalla primero antes de interactuar. Sé preciso con las coordenadas."""
        
        self.model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=[android_control_tool],
            system_instruction=system_instruction or default_instruction
        )
        
        self.chat = None
        self._start_new_chat()
    
    def _start_new_chat(self):
        """Inicia una nueva sesión de chat"""
        self.chat = self.model.start_chat(
            enable_automatic_function_calling=False  # Manual para controlar el WebSocket
        )
    
    def reset_chat(self):
        """Reinicia la conversación"""
        self._start_new_chat()
    
    async def process_message(self, user_message: str) -> Dict[str, Any]:
        """
        Procesa un mensaje del usuario y retorna la respuesta o comando.
        
        Args:
            user_message: Mensaje del usuario
        
        Returns:
            Dict con:
                - type: 'text' | 'command' | 'error'
                - content: El texto de respuesta o el comando JSON
                - function_name: (opcional) nombre de la función si es comando
        """
        try:
            response = self.chat.send_message(user_message)
            
            # Verificar si hay function call
            if (response.candidates and 
                response.candidates[0].content.parts and
                hasattr(response.candidates[0].content.parts[0], 'function_call') and
                response.candidates[0].content.parts[0].function_call):
                
                fc = response.candidates[0].content.parts[0].function_call
                function_name = fc.name
                
                # Convertir args a dict normal
                args = dict(fc.args) if fc.args else {}
                
                # Construir el comando JSON
                command_payload = build_command_payload(function_name, args)
                
                if command_payload:
                    return {
                        "type": "command",
                        "content": command_payload,
                        "function_name": function_name,
                        "args": args
                    }
                else:
                    return {
                        "type": "error",
                        "content": f"Función desconocida: {function_name}"
                    }
            
            # Si no hay function call, es una respuesta de texto
            return {
                "type": "text",
                "content": response.text
            }
            
        except Exception as e:
            return {
                "type": "error",
                "content": str(e)
            }
    
    def provide_function_result(self, function_name: str, result: Any):
        """
        Proporciona el resultado de una función ejecutada al modelo.
        Usar después de ejecutar un comando en el dispositivo.
        
        Args:
            function_name: Nombre de la función que se ejecutó
            result: Resultado de la ejecución (ej: UI tree JSON)
        """
        from google.generativeai.types import content_types
        
        # Crear respuesta de función para el modelo
        function_response = content_types.to_content({
            "function_response": {
                "name": function_name,
                "response": {"result": result}
            }
        })
        
        # Enviar al chat para mantener el contexto
        self.chat.send_message(function_response)


# ==========================================
# Instancia Global del Agente
# ==========================================

# Singleton para usar en el servidor
_agent_instance: Optional[AIAgent] = None

def get_ai_agent() -> AIAgent:
    """
    Obtiene la instancia global del agente de IA.
    Crea una nueva si no existe.
    """
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AIAgent()
    return _agent_instance


def create_agent_for_session(system_instruction: Optional[str] = None) -> AIAgent:
    """
    Crea un nuevo agente para una sesión específica.
    Útil cuando necesitas múltiples conversaciones independientes.
    """
    return AIAgent(system_instruction=system_instruction)
