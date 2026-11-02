-- EmployeeData: one row per routed employee document. ClassificationResults: see below.
--
-- Run in the Azure portal: SQL database > Query editor (preview).
-- The app also creates this table automatically if it is missing; this script
-- lets you create and review it by hand. Keep it in step with
-- src/hr_onboarding/storage/sql_repository.py.

IF OBJECT_ID(N'dbo.EmployeeData', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.EmployeeData (
        Id                     INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_EmployeeData PRIMARY KEY,
        PersonKey              NVARCHAR(64)      NOT NULL,
        FileName               NVARCHAR(255)     NOT NULL,
        FullName               NVARCHAR(200)     NULL,
        DateOfBirth            DATE              NULL,
        StatedAge              INT               NULL,
        CalculatedAge          INT               NULL,
        AgeMismatch            BIT               NULL,
        RightToWorkStatus      NVARCHAR(200)     NULL,
        RightToWorkExpiry      DATE              NULL,
        PreviousEmploymentJson NVARCHAR(MAX)     NULL,
        BlobUrl                NVARCHAR(1000)    NULL,
        Confidence             FLOAT             NULL,
        Status                 NVARCHAR(20)      NOT NULL,
        Issues                 NVARCHAR(MAX)     NULL,
        ProcessedAt            DATETIME2         NOT NULL,  -- UTC
        -- Matches the per-person blob path: employee-documents/<PersonKey>/<FileName>
        CONSTRAINT UQ_EmployeeData_PersonKey_FileName UNIQUE (PersonKey, FileName)
    );
END;

-- ClassificationResults: latest classification of every document (routed or
-- left in incoming for review). Feeds the report's Classification sheet.
IF OBJECT_ID(N'dbo.ClassificationResults', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ClassificationResults (
        Id          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ClassificationResults PRIMARY KEY,
        Location    NVARCHAR(400)     NOT NULL,  -- "container/path" where the file lives now
        FileName    NVARCHAR(255)     NOT NULL,
        Category    NVARCHAR(32)      NULL,
        Confidence  FLOAT             NULL,
        Reason      NVARCHAR(MAX)     NULL,
        PersonKey   NVARCHAR(64)      NOT NULL,
        Status      NVARCHAR(20)      NOT NULL,
        Issues      NVARCHAR(MAX)     NULL,
        ProcessedAt DATETIME2         NOT NULL,  -- UTC
        CONSTRAINT UQ_ClassificationResults_Location UNIQUE (Location)
    );
END;
