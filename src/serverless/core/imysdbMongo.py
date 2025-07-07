import os
from pymongo import MongoClient

class IMYDB:
    def __init__(self, file_path):
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'DB')  # Default to 'DB' if not set
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]  # DB Name
        self.collection = self.db[self._sanitize_collection_name(file_path)]
    
    def _sanitize_collection_name(self, file_path):
        return file_path.replace('/', '_').replace('.json', '')

    def set(self, key, value):
        """Set a key-value pair in the database."""
        self.collection.update_one(
            {'_id': key},
            {'$set': {'value': value}},
            upsert=True
        )

    def get(self, key, default=None):
        """Get a value by key, or return default."""
        doc = self.collection.find_one({'_id': key})
        if doc:
            return doc['value']
        return default

    def delete(self, key):
        """Delete a key-value pair."""
        self.collection.delete_one({'_id': key})

    def update(self, key, value):
        """Update the value of an existing key."""
        if self.exists(key):
            self.set(key, value)

    def exists(self, key):
        """Check if the key exists."""
        return self.collection.count_documents({'_id': key}) > 0
