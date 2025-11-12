-- Step 1: Try to create pgvector extension with specific schema targeting
-- This will work if pgvector is available in the Neon instance

-- Method 1: Try direct creation
CREATE EXTENSION IF NOT EXISTS pgvector SCHEMA public;

-- If above fails, try alternative methods:

-- Method 2: Check if extension exists in system catalog and install
DO $$
BEGIN
    -- Check if pgvector is available
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pgvector') THEN
        CREATE EXTENSION IF NOT EXISTS pgvector;
        RAISE NOTICE 'pgvector extension created successfully';
    ELSE
        RAISE NOTICE 'pgvector extension not available in this Neon instance';
        RAISE NOTICE 'Please enable pgvector through Neon Console: console.neon.tech';
    END IF;
END $$;

-- Check if extension was successfully created
SELECT 
    extname as extension_name,
    extversion as version,
    n.nspname as schema_name
FROM pg_extension e
JOIN pg_namespace n ON e.extnamespace = n.oid
WHERE extname = 'pgvector';

-- If pgvector is available, this will show the extension info
-- If not, you'll need to enable it through Neon Console first