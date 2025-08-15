# 前端开发指南

## 代码维护规范

为了保持代码库的清洁和高效开发，请遵循以下规范：

### 导入语句规范

1. **禁止在导入语句中包含文件扩展名**
   ```typescript
   // 正确
   import { Component } from './Component';
   
   // 错误
   import { Component } from './Component.ts';
   import { Component } from './Component.tsx';
   ```

### 编译生成文件管理

1. **使用clean命令清理编译生成的文件**
   ```bash
   npm run clean
   ```
   
   此命令会删除：
   - `src`目录中的所有`.js`文件
   - 项目根目录中的`.tsbuildinfo`文件
   - 项目中的`.d.ts`文件（除了`node_modules`中的）

2. **遵守`.gitignore`规则**
   已配置`.gitignore`忽略所有编译生成的文件，请不要将这些文件提交到代码仓库。

### TypeScript项目管理

1. **只修改TypeScript源文件**
   所有的代码修改应该只针对`.ts`和`.tsx`文件，不要直接修改任何`.js`文件。

2. **构建前先清理**
   在执行生产构建前，建议先执行清理：
   ```bash
   npm run clean && npm run build
   ```

### 避免的常见问题

1. **配置文件冗余**
   不要同时维护相同配置的`.js`和`.ts`版本，例如：
   - 避免同时存在`vite.config.js`和`vite.config.ts`
   
2. **导入冲突**
   如果发现导入相关的错误，检查：
   - 是否在导入语句中包含了文件扩展名（应去除）
   - 是否存在同名的`.js`和`.ts`文件（应只保留`.ts`版本）

## 开发流程

1. 本地开发使用：
   ```bash
   npm run dev
   ```

2. 构建生产版本：
   ```bash
   npm run clean && npm run build
   ```

3. 代码检查：
   ```bash
   npm run lint
   ``` 