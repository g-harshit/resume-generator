-- Runs once, when the volume is first created. The test suite gets its own
-- database so running pytest never touches dev data.
CREATE DATABASE resume_test OWNER resume;
