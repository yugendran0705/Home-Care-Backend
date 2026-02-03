class DefinedError(Exception):
    """Custom error class for defined errors."""
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
    
    def __repr__(self):
        return f"DefinedError(status_code={self.status_code}, message={self.message})"

    def __str__(self):
        return f"DefinedError: {self.message}"