import requests
import sys

URL_base = "http://127.0.0.1:8000"

# ==========================================
# Ejemplo 1: Crear una nueva key
# ==========================================
def test_create_key(token: str):
    """
    Crea una nueva API key para el usuario autenticado
    
    Args:
        token: Token de Firebase Authentication (ID Token)
    """
    CREATE_ENDPOINT = f"{URL_base}/keys/create"
    
    print("🔑 Creando nueva API Key...")
    print("=" * 60)
    
    # Datos de la nueva key
    new_key = {
        "device": "Production Server",
        "name": "OpenAI API Key",
        "reserved": True,
        "secretKey": "sk-proj-1234567890abcdefghijklmnop"
    }
    
    # Headers con autenticación
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(CREATE_ENDPOINT, json=new_key, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data.get('success')}")
            print(f"📝 Mensaje: {data.get('message')}")
            print(f"🆔 Key ID: {data.get('key_id')}")
            print("\n📊 Datos guardados:")
            print("-" * 60)
            key_data = data.get('data', {})
            for field, value in key_data.items():
                # Ocultar parcialmente la secretKey
                if field == 'secretKey' and isinstance(value, str) and len(value) > 10:
                    display_value = value[:8] + "..." + value[-4:]
                else:
                    display_value = value
                print(f"  {field}: {display_value}")
            
            print("\n" + "=" * 60)
            return data
            
        elif response.status_code == 401:
            error_data = response.json()
            print(f"❌ Error de autenticación (401)")
            print(f"   Detalle: {error_data.get('detail')}")
            return None
            
        elif response.status_code == 422:
            error_data = response.json()
            print(f"❌ Error de validación (422)")
            print(f"   Los datos enviados no son válidos:")
            for error in error_data.get('detail', []):
                print(f"   - {error.get('loc')}: {error.get('msg')}")
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
# Ejemplo 2: Crear múltiples keys
# ==========================================
def test_create_multiple_keys(token: str):
    """
    Crear varias keys de ejemplo
    """
    CREATE_ENDPOINT = f"{URL_base}/keys/create"
    
    print("\n🔑 Creando múltiples API Keys...")
    print("=" * 60)
    
    # Lista de keys para crear
    keys_to_create = [
        {
            "device": "Development Server",
            "name": "OpenAI Dev Key",
            "reserved": False,
            "secretKey": "sk-dev-abcdefghijklmnop"
        },
        {
            "device": "Mobile App",
            "name": "Anthropic Claude API",
            "reserved": True,
            "secretKey": "sk-ant-api-xxxxxxxxxxxxxx"
        },
        {
            "device": "Web Dashboard",
            "name": "Google Gemini Key",
            "reserved": False,
            "secretKey": "AIzaSyxxxxxxxxxxxxxxxxxxxxxx"
        }
    ]
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    created_keys = []
    
    for i, key_data in enumerate(keys_to_create, 1):
        print(f"\n📝 Creando key {i}/{len(keys_to_create)}: {key_data['name']}")
        
        try:
            response = requests.post(CREATE_ENDPOINT, json=key_data, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Creada exitosamente - ID: {data.get('key_id')}")
                created_keys.append(data)
            else:
                print(f"   ❌ Error {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print(f"✅ Keys creadas: {len(created_keys)}/{len(keys_to_create)}")
    
    return created_keys


# ==========================================
# Ejemplo 3: Crear y luego listar
# ==========================================
def test_create_and_list(token: str):
    """
    Crear una key y luego listar todas las keys del usuario
    """
    print("\n🧪 Test: Crear key y luego listar...")
    print("=" * 60)
    
    # 1. Crear una key
    new_key = {
        "device": "Test Device",
        "name": "Test API Key",
        "reserved": False,
        "secretKey": "sk-test-1234567890"
    }
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print("Paso 1: Creando key...")
    response = requests.post(f"{URL_base}/keys/create", json=new_key, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Key creada con ID: {data.get('key_id')}")
    else:
        print(f"❌ Error al crear: {response.status_code}")
        return
    
    # 2. Listar todas las keys
    print("\nPaso 2: Listando todas las keys del usuario...")
    response = requests.get(f"{URL_base}/keys/list", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Total de keys: {data.get('count')}")
        print(f"👤 User ID: {data.get('user_id')}")
    else:
        print(f"❌ Error al listar: {response.status_code}")
    
    print("=" * 60)


# ==========================================
# Ejecutar pruebas
# ==========================================
if __name__ == "__main__":
    print("🔥 Probando endpoint de CREAR keys con Autenticación\n")
    
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
        
        print("Opciones de prueba:")
        print("  1. Crear una key")
        print("  2. Crear múltiples keys")
        print("  3. Crear y luego listar")
        print("  4. Todas las anteriores")
        print()
        
        choice = input("Elige una opción (1/2/3/4): ").strip()
        
        if choice == "1":
            test_create_key(token)
        elif choice == "2":
            test_create_multiple_keys(token)
        elif choice == "3":
            test_create_and_list(token)
        elif choice == "4":
            test_create_key(token)
            test_create_multiple_keys(token)
            test_create_and_list(token)
        else:
            print("❌ Opción inválida")
    
    else:
        # Opción 2: Token interactivo
        token = input("🔑 Pega tu token de Firebase aquí: ").strip()
        
        if token:
            print()
            try:
                test_create_key(token)
                
                print("\n¿Quieres crear más keys? (s/n): ", end="")
                if input().strip().lower() == 's':
                    test_create_multiple_keys(token)
                
            except Exception as e:
                print(f"❌ Error inesperado: {e}")
        else:
            print("❌ No se proporcionó ningún token")
    
    print("\n✅ Pruebas completadas!")
    print("\n💡 Para usar el token desde línea de comandos:")
    print("   python test/test_create_keys.py <tu_token>")
