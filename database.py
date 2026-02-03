"""
ניהול חיבור למסד נתונים MongoDB עם Async API
"""
from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure
import config

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        
    async def connect(self):
        """יצירת חיבור למונגו"""
        try:
            self.client = AsyncMongoClient(config.MONGO_URI)
            # בדיקת חיבור
            await self.client.admin.command('ping')
            self.db = self.client[config.DB_NAME]
            print("✅ התחברות למונגו הצליחה")
            
            # יצירת אינדקסים
            await self.db.services.create_index("service_id", unique=True)
            await self.db.services.create_index("owner_id")
            await self.db.services.create_index("owners")

            # מיגרציה לאחור: אם יש owner_id אבל אין owners, ניצור owners=[owner_id]
            # (כדי לאפשר לכמה אדמינים לראות את אותו השירות בלי "לדרוס" בעלות)
            await self.db.services.update_many(
                {"owner_id": {"$exists": True}, "owners": {"$exists": False}},
                [{"$set": {"owners": ["$owner_id"]}}],
            )
            
        except ConnectionFailure as e:
            print(f"❌ שגיאה בהתחברות למונגו: {e}")
            raise
    
    async def close(self):
        """סגירת החיבור"""
        if self.client:
            self.client.close()
            print("🔌 החיבור למונגו נסגר")
    
    async def add_service(self, service_id: str, name: str, owner_id: int):
        """הוספת שירות חדש"""
        result = await self.db.services.update_one(
            {"service_id": service_id},
            {
                # לא "לדרוס" בעלות קיימת; רק להוסיף אדמין לרשימת owners
                "$set": {"service_id": service_id, "name": name},
                "$setOnInsert": {"status": "unknown"},
                "$addToSet": {"owners": owner_id},
            },
            upsert=True
        )
        return result
    
    async def get_services(self, owner_id: int = None):
        """קבלת רשימת שירותים"""
        if owner_id:
            # תמיכה גם ב-owner_id הישן וגם ב-owners החדש
            query = {"$or": [{"owner_id": owner_id}, {"owners": owner_id}]}
        else:
            query = {}
        cursor = self.db.services.find(query)
        return await cursor.to_list(length=100)
    
    async def get_service(self, service_id: str):
        """קבלת שירות ספציפי"""
        return await self.db.services.find_one({"service_id": service_id})
    
    async def update_service_status(self, service_id: str, status: str):
        """עדכון סטטוס שירות"""
        await self.db.services.update_one(
            {"service_id": service_id},
            {"$set": {"status": status}}
        )
    
    async def delete_service(self, service_id: str):
        """מחיקת שירות"""
        result = await self.db.services.delete_one({"service_id": service_id})
        return result.deleted_count > 0
    
    async def log_action(self, service_id: str, action: str, user_id: int, success: bool, message: str = None):
        """שמירת לוג של פעולה"""
        log = {
            "service_id": service_id,
            "action": action,
            "user_id": user_id,
            "success": success,
            "message": message,
            "timestamp": None  # MongoDB יוסיף timestamp אוטומטי
        }
        await self.db.logs.insert_one(log)

# אובייקט גלובלי
db = Database()
