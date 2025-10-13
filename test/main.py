import requests
import os

URL_base = "http://127.0.0.1:8000"

# ==========================================
# Example 1: upload an image from file
# ==========================================
def test_upload_image():
    """Upload a JPG image"""
    UPLOAD_ENDPOINT = f"{URL_base}/storage/upload"
    
    image_path = "test/img/example.jpg"
    
    # option 1: Upload to the root of the bucket
    with open(image_path, "rb") as file:
        response = requests.post(
            UPLOAD_ENDPOINT,
            files={"file": ("example.jpg", file, "image/jpeg")}
        )

    print("📤 Upload Response (root):")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}\n")

    # option 2: Upload to a specific folder
    with open(image_path, "rb") as file:
        response = requests.post(
            f"{UPLOAD_ENDPOINT}?folder=imagenes/prueba",
            files={"file": ("example.jpg", file, "image/jpeg")}
        )
    
    print("📤 Upload Response (con carpeta):")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}\n")
    
    return response.json()


# ==========================================
# Example 2: upload different types of files
# ==========================================
def test_upload_different_files():
    """Examples with different file types"""
    UPLOAD_ENDPOINT = f"{URL_base}/storage/upload"
    
    # PDF
    # with open("documento.pdf", "rb") as file:
    #     response = requests.post(
    #         f"{UPLOAD_ENDPOINT}?folder=documentos",
    #         files={"file": ("documento.pdf", file, "application/pdf")}
    #     )
    
    # TXT
    # with open("archivo.txt", "rb") as file:
    #     response = requests.post(
    #         UPLOAD_ENDPOINT,
    #         files={"file": ("archivo.txt", file, "text/plain")}
    #     )
    
    # JSON
    # with open("data.json", "rb") as file:
    #     response = requests.post(
    #         UPLOAD_ENDPOINT,
    #         files={"file": ("data.json", file, "application/json")}
    #     )
    
    pass


# ==========================================
# Example 3: List files
# ==========================================
def test_list_files():
    """List all files"""
    LIST_ENDPOINT = f"{URL_base}/storage/list"
    
    response = requests.get(LIST_ENDPOINT)
    
    print("📋 List of files:")
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Total: {data.get('count')} files\n")

    for file in data.get('files', []):
        print(f"  - {file['name']} ({file['size_bytes']} bytes)")
    
    return data


# ==========================================
# Example 4: Download a file
# ==========================================
def test_download_file(file_path):
    """Download a specific file"""
    DOWNLOAD_ENDPOINT = f"{URL_base}/storage/download/{file_path}"
    
    response = requests.get(DOWNLOAD_ENDPOINT)
    
    if response.status_code == 200:
        # Guardar el archivo descargado
        output_filename = f"downloaded_{file_path.split('/')[-1]}"
        with open(output_filename, "wb") as f:
            f.write(response.content)
        print(f"✅ Archivo descargado: {output_filename}")
    else:
        print(f"❌ Error al descargar: {response.status_code}")
        print(response.json())


# ==========================================
# Example 5: Generate signed URL
# ==========================================
def test_get_signed_url(file_path):
    """Get temporary URL for a file"""
    URL_ENDPOINT = f"{URL_base}/storage/url/{file_path}"
    
    response = requests.get(
        URL_ENDPOINT,
        params={"expiration_minutes": 30}
    )
    
    print(f"🔗 URL firmada:")
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"URL: {data['signed_url']}")
        print(f"Expira en: {data['expires_in_minutes']} minutos\n")
    
    return response.json()


# ==========================================
# Example 6: Delete a file
# ==========================================
def test_delete_file(file_path):
    """Delete a file from storage"""
    DELETE_ENDPOINT = f"{URL_base}/storage/delete/{file_path}"
    
    response = requests.delete(DELETE_ENDPOINT)
    
    print(f"🗑️ Delete file:")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}\n")


# ==========================================
# Execute Tests
# ==========================================
if __name__ == "__main__":
    print("🚀 Starting Firebase Storage API tests\n")
    print("=" * 50)

    # 1. Upload image
    try:
        upload_result = test_upload_image()
        uploaded_file_path = upload_result.get('file_path')
    except Exception as e:
        print(f"❌ Error uploading: {e}\n")
        uploaded_file_path = None
    
    print("=" * 50)

    # 2. List files
    try:
        test_list_files()
    except Exception as e:
        print(f"❌ Error listing: {e}\n")

    print("=" * 50)

    # 3. Download file
    if uploaded_file_path:
        try:
            test_download_file(uploaded_file_path)
        except Exception as e:
            print(f"❌ Error downloading: {e}\n")
    
    print("=" * 50)

    # 4. Get signed URL
    if uploaded_file_path:
        try:
            test_get_signed_url(uploaded_file_path)
        except Exception as e:
            print(f"❌ Error getting signed URL: {e}\n")
    
    print("=" * 50)
    
   
    
    print("✅ Pruebas completadas!")