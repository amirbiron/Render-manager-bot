"""
אינטראקציה עם Render API
"""
import httpx
import config
from typing import Optional, Dict, Any

class RenderAPI:
    def __init__(self):
        self.base_url = config.RENDER_API_BASE
        self.headers = {
            "Authorization": f"Bearer {config.RENDER_API_KEY}",
            "Content-Type": "application/json"
        }
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """בקשה כללית ל-API"""
        url = f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    **kwargs
                )
                response.raise_for_status()
                
                # Render API מחזיר JSON
                if response.content:
                    return response.json()
                return {}
                
            except httpx.HTTPStatusError as e:
                print(f"❌ שגיאת HTTP: {e.response.status_code} - {e.response.text}")
                return None
            except httpx.RequestError as e:
                print(f"❌ שגיאת בקשה: {e}")
                return None
            except Exception as e:
                print(f"❌ שגיאה כללית: {e}")
                return None
    
    async def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """קבלת פרטי שירות"""
        return await self._request("GET", f"/services/{service_id}")
    
    async def suspend_service(self, service_id: str) -> bool:
        """השעיית שירות"""
        result = await self._request("POST", f"/services/{service_id}/suspend")
        return result is not None
    
    async def resume_service(self, service_id: str) -> bool:
        """המשך שירות"""
        result = await self._request("POST", f"/services/{service_id}/resume")
        return result is not None
    
    async def restart_service(self, service_id: str) -> bool:
        """הפעלה מחדש של שירות"""
        result = await self._request("POST", f"/services/{service_id}/restart")
        return result is not None
    
    async def get_service_status(self, service_id: str) -> str:
        """קבלת סטטוס שירות"""
        service = await self.get_service(service_id)
        if not service:
            return "unknown"
        
        # Render מחזיר suspended או suspended בתוך service
        if isinstance(service, dict):
            # ייתכן שהמידע נמצא בתוך service.service
            if "service" in service:
                service = service["service"]
            
            suspended = service.get("suspended", False)
            if suspended == "suspended" or suspended is True:
                return "suspended"
            return "active"
        
        return "unknown"
    
    def status_emoji(self, status: str) -> str:
        """המרת סטטוס לאימוג'י"""
        statuses = {
            "active": "🟢",
            "suspended": "🔴",
            "unknown": "⚪",
            "deploying": "🟡"
        }
        return statuses.get(status, "⚪")

# אובייקט גלובלי
render_api = RenderAPI()
