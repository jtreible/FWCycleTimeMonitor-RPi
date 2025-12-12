-- SQL script to add M218 machine to the FWCycleDashboard database
-- Machine: M218
-- IP: 192.168.0.81
-- PoE Switch: 192.168.0.84, Port: 5
-- Group: Low Bay
-- API Key: 0mu2Erjjx4fALdPxktb8Ezj1SpWjGFl7_nigks9mSAM

-- First, create the "Low Bay" group if it doesn't exist
INSERT OR IGNORE INTO MachineGroups (Name, CreatedAt)
VALUES ('Low Bay', datetime('now'));

-- Add the M218 machine
-- Note: Adjust the GroupId if needed (this assumes Low Bay will have an auto-generated ID)
INSERT INTO Machines (
    MachineId,
    IpAddress,
    Port,
    ApiKey,
    Location,
    Description,
    GroupId,
    UseHttps,
    PoESwitchIp,
    PoESwitchPort,
    CreatedAt
)
VALUES (
    'M218',
    '192.168.0.81',
    8443,
    '0mu2Erjjx4fALdPxktb8Ezj1SpWjGFl7_nigks9mSAM',
    NULL,
    NULL,
    (SELECT Id FROM MachineGroups WHERE Name = 'Low Bay' LIMIT 1),
    0,
    '192.168.0.84',
    5,
    datetime('now')
);
