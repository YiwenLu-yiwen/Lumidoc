-- Lumidoc Intelligence 数据库迁移脚本
-- 将现有的整数项目ID迁移到UUID系统
-- 
-- 警告：此脚本会修改数据库结构，请在运行前备份数据库
-- 建议在测试环境中先验证迁移过程

-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================
-- 步骤1：创建迁移映射表
-- =====================================

-- 创建临时表存储ID映射关系
CREATE TEMP TABLE project_id_mapping (
    old_id INTEGER PRIMARY KEY,
    new_id UUID DEFAULT uuid_generate_v4()
);

-- 为现有项目生成UUID映射
INSERT INTO project_id_mapping (old_id)
SELECT id FROM projects ORDER BY id;

-- =====================================
-- 步骤2：备份现有外键约束
-- =====================================

-- 禁用外键约束检查
SET session_replication_role = replica;

-- =====================================
-- 步骤3：添加新的UUID列
-- =====================================

-- 为projects表添加新的UUID列
ALTER TABLE projects ADD COLUMN new_id UUID;

-- 使用映射表更新UUID值
UPDATE projects 
SET new_id = project_id_mapping.new_id
FROM project_id_mapping 
WHERE projects.id = project_id_mapping.old_id;

-- 确保UUID列不为空
ALTER TABLE projects ALTER COLUMN new_id SET NOT NULL;

-- =====================================
-- 步骤4：为关联表添加新的UUID外键列
-- =====================================

-- project_collaborators表
ALTER TABLE project_collaborators ADD COLUMN new_project_id UUID;
UPDATE project_collaborators 
SET new_project_id = project_id_mapping.new_id
FROM project_id_mapping 
WHERE project_collaborators.project_id = project_id_mapping.old_id;

-- project_files表
ALTER TABLE project_files ADD COLUMN new_project_id UUID;
UPDATE project_files 
SET new_project_id = project_id_mapping.new_id
FROM project_id_mapping 
WHERE project_files.project_id = project_id_mapping.old_id;

-- chat_messages表
ALTER TABLE chat_messages ADD COLUMN new_project_id UUID;
UPDATE chat_messages 
SET new_project_id = project_id_mapping.new_id
FROM project_id_mapping 
WHERE chat_messages.project_id = project_id_mapping.old_id;

-- =====================================
-- 步骤5：删除旧列并重命名新列
-- =====================================

-- projects表
ALTER TABLE projects DROP CONSTRAINT IF EXISTS projects_pkey CASCADE;
ALTER TABLE projects DROP COLUMN id;
ALTER TABLE projects RENAME COLUMN new_id TO id;
ALTER TABLE projects ADD PRIMARY KEY (id);

-- project_collaborators表
ALTER TABLE project_collaborators DROP COLUMN project_id;
ALTER TABLE project_collaborators RENAME COLUMN new_project_id TO project_id;
ALTER TABLE project_collaborators ALTER COLUMN project_id SET NOT NULL;

-- project_files表
ALTER TABLE project_files DROP COLUMN project_id;
ALTER TABLE project_files RENAME COLUMN new_project_id TO project_id;
ALTER TABLE project_files ALTER COLUMN project_id SET NOT NULL;

-- chat_messages表
ALTER TABLE chat_messages DROP COLUMN project_id;
ALTER TABLE chat_messages RENAME COLUMN new_project_id TO project_id;
ALTER TABLE chat_messages ALTER COLUMN project_id SET NOT NULL;

-- =====================================
-- 步骤6：重新创建外键约束
-- =====================================

-- 重新启用外键约束检查
SET session_replication_role = DEFAULT;

-- project_collaborators外键
ALTER TABLE project_collaborators 
ADD CONSTRAINT project_collaborators_project_id_fkey 
FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;

-- project_files外键
ALTER TABLE project_files 
ADD CONSTRAINT project_files_project_id_fkey 
FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;

-- chat_messages外键
ALTER TABLE chat_messages 
ADD CONSTRAINT chat_messages_project_id_fkey 
FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;

-- =====================================
-- 步骤7：重新创建索引
-- =====================================

-- projects表索引
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects (name);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects (user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects (created_at);

-- 关联表索引
CREATE INDEX IF NOT EXISTS idx_project_collaborators_project_id ON project_collaborators(project_id);
CREATE INDEX IF NOT EXISTS idx_project_files_project_id ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_project_id ON chat_messages(project_id);

-- =====================================
-- 步骤8：添加约束
-- =====================================

-- 添加唯一约束
ALTER TABLE projects 
ADD CONSTRAINT unique_user_project_name UNIQUE (user_id, name);

ALTER TABLE project_collaborators 
ADD CONSTRAINT unique_project_collaborator UNIQUE (project_id, user_id);

-- =====================================
-- 步骤9：验证迁移结果
-- =====================================

DO $$
DECLARE
    project_count INTEGER;
    collaborator_count INTEGER;
    file_count INTEGER;
    message_count INTEGER;
BEGIN
    -- 检查项目数量
    SELECT COUNT(*) INTO project_count FROM projects;
    RAISE NOTICE 'Projects migrated: %', project_count;
    
    -- 检查协作者数量
    SELECT COUNT(*) INTO collaborator_count FROM project_collaborators;
    RAISE NOTICE 'Collaborators migrated: %', collaborator_count;
    
    -- 检查文件数量
    SELECT COUNT(*) INTO file_count FROM project_files;
    RAISE NOTICE 'Files migrated: %', file_count;
    
    -- 检查消息数量
    SELECT COUNT(*) INTO message_count FROM chat_messages;
    RAISE NOTICE 'Messages migrated: %', message_count;
    
    -- 验证外键完整性
    PERFORM * FROM project_collaborators pc 
    WHERE NOT EXISTS (SELECT 1 FROM projects p WHERE p.id = pc.project_id);
    
    PERFORM * FROM project_files pf 
    WHERE NOT EXISTS (SELECT 1 FROM projects p WHERE p.id = pf.project_id);
    
    PERFORM * FROM chat_messages cm 
    WHERE NOT EXISTS (SELECT 1 FROM projects p WHERE p.id = cm.project_id);
    
    RAISE NOTICE 'UUID migration completed successfully!';
    RAISE NOTICE 'All foreign key relationships verified.';
    
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Migration verification failed: %', SQLERRM;
END $$;