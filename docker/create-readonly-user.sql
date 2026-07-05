-- Anti-hallucination safety net: the application connects with this login,
-- never with sa, so even a malformed/destructive generated query is blocked
-- by SQL Server permissions rather than relying on the app layer alone.

USE master;
GO

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'filaks_readonly')
BEGIN
    CREATE LOGIN filaks_readonly WITH PASSWORD = 'Filaks!ReadOnly2026';
END
GO

USE FilaksOne;
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'filaks_readonly')
BEGIN
    CREATE USER filaks_readonly FOR LOGIN filaks_readonly;
END
GO

ALTER ROLE db_datareader ADD MEMBER filaks_readonly;
GO
