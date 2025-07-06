import json
import os

class IMYDB:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = {}  # Initialize self.data to an empty dictionary
        self.load_data()  # Load the data after initializing self.data

    def load_data(self):
        """Load data from the JSON file or create the file with empty data if it doesn't exist."""
        dir_path = os.path.dirname(self.file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        if not os.path.exists(self.file_path):
            # If file doesn't exist, create it with an empty dictionary
            print(f"{self.file_path} does not exist, creating new file.")
            self.save_data()  # Save an empty dictionary to create the file
        else:
            with open(self.file_path, 'r') as f:
                content = f.read().strip()
                if content:  # File is not empty
                    try:
                        self.data = json.loads(content)  # Try to load the JSON
                    except json.JSONDecodeError:
                        print(f"Warning: Invalid JSON in {self.file_path}, initializing with empty data.")
                        self.data = {}  # Initialize with an empty dictionary if JSON is invalid
                else:
                    print(f"Warning: {self.file_path} is empty, initializing with empty data.")
                    self.data = {}  # Initialize with an empty dictionary if the file is empty

    def save_data(self):
        """Save current data back to the JSON file."""
        dir_path = os.path.dirname(self.file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(self.file_path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def set(self, key, value):
        """Set a key-value pair in the data."""
        self._set_nested(self.data, key.split('.'), value)
        self.save_data()

    def get(self, key, default=None):
        """Get a value by key, or return default if key is not found."""
        return self._get_nested(self.data, key.split('.'), default)

    def delete(self, key):
        """Delete a key-value pair."""
        self._delete_nested(self.data, key.split('.'))
        self.save_data()

    def update(self, key, value):
        """Update the value of an existing key."""
        if self.exists(key):
            self.set(key, value)

    def exists(self, key):
        """Check if the key exists in the data."""
        return self._get_nested(self.data, key.split('.'), default=None) is not None

    # Helper methods for handling nested structures

    def _set_nested(self, data, keys, value):
        """Set a value in a nested structure."""
        key = keys[0]
        if len(keys) == 1:
            data[key] = value
        else:
            if key not in data:
                data[key] = {}
            self._set_nested(data[key], keys[1:], value)

    def _get_nested(self, data, keys, default=None):
        """Get a value from a nested structure."""
        key = keys[0]
        if len(keys) == 1:
            return data.get(key, default)
        elif key in data:
            return self._get_nested(data[key], keys[1:], default)
        return default

    def _delete_nested(self, data, keys):
        """Delete a key-value pair in a nested structure."""
        key = keys[0]
        if len(keys) == 1:
            if key in data:
                del data[key]
        elif key in data:
            self._delete_nested(data[key], keys[1:])