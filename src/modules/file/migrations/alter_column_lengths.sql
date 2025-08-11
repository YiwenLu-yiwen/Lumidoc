-- 修改project_files表中字段长度
-- 增加name字段长度限制
ALTER TABLE project_files ALTER COLUMN name TYPE VARCHAR(255);

-- 增加type字段长度限制
ALTER TABLE project_files ALTER COLUMN type TYPE VARCHAR(100);

-- 确保file_hash字段为TEXT类型（无长度限制）
ALTER TABLE project_files ALTER COLUMN file_hash TYPE TEXT;

-- 确保path字段为TEXT类型（无长度限制）
ALTER TABLE project_files ALTER COLUMN path TYPE TEXT; 