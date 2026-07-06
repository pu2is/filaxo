SET NOCOUNT ON;

IF OBJECT_ID('tempdb..#FileList') IS NOT NULL DROP TABLE #FileList;

-- Column layout for RESTORE FILELISTONLY on SQL Server 2017+ (2022 included)
CREATE TABLE #FileList (
    LogicalName          nvarchar(128),
    PhysicalName         nvarchar(260),
    Type                 char(1),
    FileGroupName        nvarchar(128) NULL,
    Size                 numeric(20,0),
    MaxSize              numeric(20,0),
    FileId               bigint,
    CreateLSN            numeric(25,0),
    DropLSN              numeric(25,0) NULL,
    UniqueId             uniqueidentifier,
    ReadOnlyLSN          numeric(25,0) NULL,
    ReadWriteLSN         numeric(25,0) NULL,
    BackupSizeInBytes    bigint,
    SourceBlockSize      int,
    FileGroupId          int,
    LogGroupGUID         uniqueidentifier NULL,
    DifferentialBaseLSN  numeric(25,0) NULL,
    DifferentialBaseGUID uniqueidentifier NULL,
    IsReadOnly           bit,
    IsPresent            bit,
    TDEThumbprint        varbinary(32) NULL,
    SnapshotUrl          nvarchar(360) NULL
);

INSERT INTO #FileList
EXEC ('RESTORE FILELISTONLY FROM DISK = N''$(BackupFile)''');

-- Backup's internal logical file names are unknown ahead of time, so the
-- MOVE clause has to be built from FILELISTONLY rather than hardcoded.
DECLARE @MoveClause nvarchar(max) = N'';
SELECT @MoveClause = @MoveClause + N', MOVE N''' + LogicalName + N''' TO N''$(DataPath)' +
       LogicalName + CASE WHEN Type = 'L' THEN N'.ldf' ELSE N'.mdf' END + N''''
FROM #FileList;

DECLARE @Sql nvarchar(max) = N'
RESTORE DATABASE [$(DbName)]
FROM DISK = N''$(BackupFile)''
WITH ' + STUFF(@MoveClause, 1, 1, N'') + N', REPLACE, STATS = 5;';

PRINT @Sql;
EXEC sp_executesql @Sql;
