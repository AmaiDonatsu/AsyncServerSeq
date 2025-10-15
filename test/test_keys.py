import requests
import sys

URL_base = "http://127.0.0.1:8000"

# ==========================================
# Ejemplo 1: Listar todas las keys CON AUTENTICACIÓN
# ==========================================
def test_list_keys_with_auth(token: str):
    """
    Obtener todas las API keys del usuario autenticado
    
    Args:
        token: Token de Firebase Authentication (ID Token)
    """
    LIST_ENDPOINT = f"{URL_base}/keys/list"
    
    print("📋 Listando API Keys desde Firestore (CON AUTENTICACIÓN)...")
    print("=" * 60)
    
    # Incluir el token en el header Authorization
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(LIST_ENDPOINT, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data.get('success')}")
            print(f"👤 User ID: {data.get('user_id')}")
            print(f"📊 Total de keys: {data.get('count')}")
            
            if data.get('count', 0) > 0:
                print("\n🔑 Keys encontradas:")
                print("-" * 60)
                
                for key in data.get('keys', []):
                    print(f"\n  ID del documento: {key.get('id')}")
                    for field, value in key.items():
                        if field != 'id':
                            # Ocultar parcialmente el valor de la key
                            if field == 'key' and isinstance(value, str) and len(value) > 10:
                                display_value = value[:8] + "..." + value[-4:]
                            else:
                                display_value = value
                            print(f"  {field}: {display_value}")
            else:
                print("\n📭 No se encontraron keys para este usuario")
            
            print("\n" + "=" * 60)
            return data
            
        elif response.status_code == 401:
            error_data = response.json()
            print(f"❌ Error de autenticación (401)")
            print(f"   Detalle: {error_data.get('detail')}")
            print("\n💡 Posibles causas:")
            print("   1. El token es inválido")
            print("   2. El token ha expirado (duran 1 hora)")
            print("   3. No se envió el header Authorization correctamente")
            return None
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Detalle: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar al servidor")
        print("   Asegúrate de que el servidor esté corriendo: python server.py")
        return None


# ==========================================
# Ejemplo 2: Probar sin autenticación (debería fallar)
# ==========================================
def test_list_keys_without_auth():
    """
    Intentar obtener keys SIN token (debe fallar con 401)
    """
    LIST_ENDPOINT = f"{URL_base}/keys/list"
    
    print("\n🧪 Probando endpoint SIN autenticación (debería fallar)...")
    print("=" * 60)
    
    # Sin header Authorization
    response = requests.get(LIST_ENDPOINT)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 401:
        print("✅ Correcto: El endpoint rechazó la petición sin token")
        error_data = response.json()
        print(f"   Mensaje: {error_data.get('detail')}")
    else:
        print("⚠️ Inesperado: El endpoint debería requerir autenticación")
    
    print("=" * 60)


# ==========================================
# Ejecutar pruebas
# ==========================================
if __name__ == "__main__":
    print("🔥 Probando endpoints de Firebase Firestore con Autenticación\n")
    
    print("=" * 60)
    print("📌 IMPORTANTE:")
    print("   Este endpoint requiere un TOKEN de Firebase Authentication")
    print("   Para obtener un token:")
    print("   1. Inicia sesión en tu frontend con Firebase Auth")
    print("   2. Ejecuta: await user.getIdToken()")
    print("   3. Copia el token y pégalo aquí")
    print("=" * 60)
    print()
    
    # Opción 1: Token como argumento
    if len(sys.argv) > 1:
        token = sys.argv[1]
        print("✅ Token recibido como argumento\n")
        test_list_keys_with_auth(token)
    else:
        # Opción 2: Token interactivo
        print("Opciones:")
        print("  1. Ingresa un token ahora")
        print("  2. Probar sin autenticación (fallará con 401)")
        print()
        
        choice = input("Elige una opción (1/2): ").strip()
        
        if choice == "1":
            print()
            token = input("🔑 Pega tu token de Firebase aquí: ").strip()
            
            if token:
                print()
                try:
                    test_list_keys_with_auth(token)
                except Exception as e:
                    print(f"❌ Error inesperado: {e}")
            else:
                print("❌ No se proporcionó ningún token")
        
        elif choice == "2":
            try:
                test_list_keys_without_auth()
            except Exception as e:
                print(f"❌ Error inesperado: {e}")
        
        else:
            print("❌ Opción inválida")
    
    print("\n✅ Pruebas completadas!")
    print("\n💡 Para usar el token desde línea de comandos:")
    print("   python test/test_keys.py <tu_token>")

