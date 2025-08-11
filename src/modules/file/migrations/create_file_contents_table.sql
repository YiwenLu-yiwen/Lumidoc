-- 创建file_contents表
CREATE TABLE IF NOT EXISTS file_contents (
    content_hash TEXT PRIMARY KEY,  -- 文件内容的SHA-256哈希值
    markdown_content TEXT NOT NULL, -- 处理后的Markdown内容
    metadata JSONB,                -- 文件元数据（如标题、作者等）
    file_type TEXT NOT NULL,       -- 文件类型
    page_count INTEGER DEFAULT 1,   -- 页数
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_file_contents_hash ON file_contents(content_hash);
CREATE INDEX IF NOT EXISTS idx_file_contents_type ON file_contents(file_type);

-- 添加触发器以自动更新updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_file_contents_updated_at
    BEFORE UPDATE ON file_contents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 修改project_files表，添加content_hash外键
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns 
        WHERE table_name = 'project_files' AND column_name = 'content_hash'
    ) THEN
        -- 添加content_hash列
        ALTER TABLE project_files ADD COLUMN content_hash TEXT REFERENCES file_contents(content_hash);
        
        -- 创建索引
        CREATE INDEX idx_project_files_content_hash ON project_files(content_hash);
        
        RAISE NOTICE 'content_hash列已添加到project_files表';
    ELSE
        RAISE NOTICE 'content_hash列已存在于project_files表中';
    END IF;
END $$; 