-- Check if interview_prep cached data columns exist
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'interview_preps' 
AND column_name LIKE '%_data'
ORDER BY column_name;
