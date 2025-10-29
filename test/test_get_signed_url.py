import requests
import sys

def test_get_signed_url():
    """
    Test interactivo para obtener una URL firmada de una imagen
    
    Requirements:
    - image_id: File Name (ej: profile.png)
    - token: Firebase Authentication Token
    """
    
    print("=" * 60)
    print("🔐 TEST: Get Signed URL")
    print("=" * 60)
    
    image_id = input("\n📷 Input name of image (ej: photo.jpg): ").strip()
    if not image_id:
        print("❌ Error: Debes proporcionar un image_id")
        sys.exit(1)

    token = input("🔑 Input Auth Token (ej: token): ").strip()
    if not token:
        print("❌ Error: Debes proporcionar un token")
        sys.exit(1)
    
    BASE_URL = "http://localhost:8000"
    endpoint = f"{BASE_URL}/files/{image_id}/signed-url"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }

    print(f"\n📡 Sending request to: {endpoint}")
    print(f"🔍 Searching for image: {image_id}")
    print("-" * 60)
    
    try:
        response = requests.get(endpoint, headers=headers)
        
        print(f"\n📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()

            print("\n✅ Signed URL obtained successfully:")
            print("-" * 60)
            
            if "signedUrl" in data:
                signed_url = data["signedUrl"]
                print(f"\n🔗 Signed URL:\n{signed_url}")
                print("\n" + "=" * 60)
                print("✓ La URL firmada se puede usar temporalmente para acceder a la imagen")
                print("=" * 60)
            else:
                print("⚠️  Response missing 'signedUrl'")
                print(f"Received data: {data}")

        elif response.status_code == 401:
            print("\n❌ Authentication error")
            print("   - Check if the token is valid")
            print("   - Make sure the token has not expired")

        elif response.status_code == 404:
            print("\n❌ Image not found")
            print(f"   - The image '{image_id}' does not exist in your storage")
            print("   - Verify the file name")

        else:
            print(f"\n❌ Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Detail: {error_data}")
            except:
                print(f"Response: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ Connection error")
        print("   - Check if the server is running at http://localhost:8000")
        print("   - Run: python server.py")

    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    test_get_signed_url()

