class DatabaseError(Exception):
    """Raised when a query fails against the database.

    Carries the driver's own error message so a retry loop can feed it back
    to the LLM as `last_sql_error` without re-parsing the original exception.
    """

    def __init__(self, message: str, *, original: Exception | None = None):
        super().__init__(message)
        self.original = original
