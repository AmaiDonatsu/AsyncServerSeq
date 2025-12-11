from fastapi import APIRouter, Request
from fastapi.routing import APIRoute, Mount

router = APIRouter(prefix="/docs-helper", tags=["Documentation Helper"])

@router.get("/site-map")
async def get_site_map(request: Request):
    """
    Devuelve una lista de todas las rutas (endpoints) registradas en la aplicación.
    Incluye path, métodos HTTP y nombre de la función.
    """
    routes_data = []
    
    for route in request.app.routes:
        route_info = {
            "path": getattr(route, "path", "N/A"),
            "name": getattr(route, "name", "N/A"),
        }
        
        # Detalles específicos según el tipo de ruta
        if isinstance(route, APIRoute):
            route_info["methods"] = sorted(list(route.methods))
            route_info["type"] = "http_route"
        elif isinstance(route, Mount):
            route_info["type"] = "mount"
            route_info["methods"] = ["N/A"]
        else:
            route_info["type"] = "other"
            route_info["methods"] = ["N/A"]
            
        routes_data.append(route_info)
        
    # Ordenar por path para facilitar la lectura
    routes_data.sort(key=lambda x: x["path"])
        
    return {
        "count": len(routes_data),
        "routes": routes_data
    }
