-- 检查file_hash列是否存在，如果不存在则添加
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns 
        WHERE table_name = 'project_files' AND column_name = 'file_hash'
    ) THEN
        -- 添加file_hash列
        ALTER TABLE project_files ADD COLUMN file_hash TEXT;
        
        -- 创建索引以提高查询性能
        CREATE INDEX idx_project_files_file_hash ON project_files(file_hash);
        
        -- 添加日志
        RAISE NOTICE 'file_hash列已添加到project_files表';
    ELSE
        RAISE NOTICE 'file_hash列已存在于project_files表中';
    END IF;
END $$; 