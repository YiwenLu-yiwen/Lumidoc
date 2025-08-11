# LightRAG 功能测试说明

本文档详细说明如何使用测试脚本来验证STP项目中LightRAG的各项功能。

## 📋 测试内容概览

### 主要测试功能
1. **单文件操作测试**
   - 添加单个Markdown文件到LightRAG
   - 查询单文件内容
   - 删除单文件
   - 测量操作时间

2. **多文件批量操作测试**
   - 批量添加多个Markdown文件
   - 列出已添加的文档
   - 多文档查询测试
   - 批量删除文档
   - 性能指标统计

3. **查询模式测试**
   - `hybrid` 模式：混合检索
   - `global` 模式：全局上下文
   - `local` 模式：局部上下文
   - `naive` 模式：简单检索

4. **性能测量**
   - 文档插入时间
   - 查询响应时间
   - 删除操作时间
   - 不同模式下的性能对比

## 🚀 快速开始

### 前置条件

1. **确保LightRAG服务运行**
   ```bash
   # 检查LightRAG服务是否启动
   curl http://localhost:8006/healthz
   
   # 如果未启动，使用以下命令启动
   cd src/modules/lightraglocal
   python main.py
   ```

2. **确保依赖服务运行**
   ```bash
   # 启动数据库服务（PostgreSQL和Neo4j）
   # 启动LLM服务
   # 具体启动方法请参考STP项目文档
   ```

### 运行测试

#### 方式一：快速测试（推荐）
```bash
# 切换到examples目录
cd examples

# 运行快速测试
python run_lightrag_test.py
```

#### 方式二：详细测试
```bash
# 切换到examples目录  
cd examples

# 运行综合测试
python test_lightrag_comprehensive.py
```

#### 方式三：自定义服务地址
```bash
# 如果LightRAG服务运行在其他地址
export LIGHTRAG_SERVICE_URL=http://your-lightrag-server:port
python run_lightrag_test.py
```

## 📊 测试结果解读

### 成功输出示例
```
==================================================
LightRAG 快速功能测试
==================================================
测试内容:
  1. 服务健康检查
  2. 单文件添加/查询/删除
  3. 多文件批量操作
  4. 不同查询模式测试
  5. 性能指标测量
==================================================
LightRAG服务地址: http://localhost:8006

✅ LightRAG服务运行正常

=== 开始单文档操作测试 ===
1. 测试单文档插入
✅ 单文档插入成功: doc_xxx, 耗时: 2.35秒
2. 测试单文档查询
✅ 查询成功，结果长度: 456, 耗时: 1.23秒
3. 测试单文档删除
✅ 文档删除成功: doc_xxx, 耗时: 0.45秒

=== 开始多文档操作测试 ===
1. 测试批量插入 3 个文档
✅ 批量插入完成，成功: 3/3, 耗时: 6.78秒
2. 测试文档列表获取
✅ 文档列表获取成功，共 3 个文档, 耗时: 0.12秒
3. 测试多文档查询
✅ 多文档查询成功，结果长度: 892, 耗时: 2.15秒
4. 测试批量文档删除
✅ 批量删除完成，成功: 3/3, 耗时: 1.34秒

=== 开始查询模式测试 ===
测试查询模式: hybrid - 溯溪鞋有什么特点？
✅ hybrid模式查询成功，耗时: 1.85秒，结果长度: 567
测试查询模式: global - 登山鞋和溯溪鞋的区别是什么？
✅ global模式查询成功，耗时: 2.10秒，结果长度: 734
测试查询模式: local - Vibram大底技术的优势？
✅ local模式查询成功，耗时: 1.42秒，结果长度: 423
测试查询模式: naive - 户外鞋类市场的发展趋势？
✅ naive模式查询成功，耗时: 0.98秒，结果长度: 312

测试结果:
  服务可用: ✅
  测试通过: 3/3
  总耗时: 18.5秒

🎉 所有测试通过！
```

### 性能基准参考

| 操作类型 | 预期时间范围 | 说明 |
|---------|-------------|------|
| 单文档插入 | 1-5秒 | 取决于文档大小和复杂度 |
| 单文档查询 | 0.5-3秒 | 取决于查询复杂度和模式 |
| 文档删除 | 0.1-1秒 | 通常较快 |
| 批量插入(3个文档) | 3-15秒 | 并行处理可提高效率 |

## 🔧 自定义测试内容

### 修改测试文档
编辑 `test_lightrag_comprehensive.py` 文件中的 `TEST_DOCUMENTS` 变量：

```python
TEST_DOCUMENTS = {
    "single_doc": {
        "content": """# 你的测试文档内容
        
        在这里放置你想要测试的Markdown内容...
        """,
        "metadata": {"type": "custom", "category": "test"}
    }
}
```

### 修改测试查询
编辑 `TEST_QUERIES` 变量：

```python
TEST_QUERIES = [
    {
        "query": "你的测试问题？",
        "expected_topics": ["关键词1", "关键词2"],
        "mode": "hybrid"
    }
]
```

## 🐛 常见问题和故障排除

### 1. 服务连接失败
```
❌ LightRAG服务不可用
```
**解决方法：**
- 检查LightRAG服务是否启动：`curl http://localhost:8006/healthz`
- 检查端口是否正确：默认8006
- 检查防火墙设置

### 2. 数据库连接错误
```
初始化LightRAG服务失败: 数据库连接错误
```
**解决方法：**
- 确保PostgreSQL服务运行
- 确保Neo4j服务运行
- 检查数据库连接配置

### 3. LLM服务不可用
```
LLM服务返回空回答
```
**解决方法：**
- 检查LLM服务是否启动
- 验证API密钥配置
- 检查网络连接

### 4. 文档插入失败
```
单文档插入失败: 内容处理错误
```
**解决方法：**
- 检查文档内容格式
- 确保文档大小在限制范围内
- 查看服务日志获取详细错误信息

### 5. 查询返回空结果
```
查询成功，结果长度: 0
```
**可能原因：**
- 文档未成功插入知识库
- 查询词与文档内容不匹配
- 需要等待索引构建完成

## 📝 测试日志分析

### 查看详细日志
测试过程中产生的详细日志位于：
- 控制台输出：实时查看测试进度
- LightRAG服务日志：`src/modules/lightraglocal/logs/`

### 日志级别说明
- `INFO`: 正常操作信息
- `WARNING`: 非致命性问题
- `ERROR`: 操作失败错误

## 🔄 集成到CI/CD

### 作为健康检查
```bash
# 在部署脚本中使用
python examples/run_lightrag_test.py
if [ $? -eq 0 ]; then
    echo "LightRAG功能正常"
else
    echo "LightRAG功能异常，部署终止"
    exit 1
fi
```

### 性能监控
定期运行测试脚本，监控LightRAG服务的性能指标：
- 响应时间趋势
- 错误率统计
- 吞吐量变化

## ⚙️ 高级配置

### 环境变量配置
```bash
# LightRAG服务地址
export LIGHTRAG_SERVICE_URL=http://localhost:8006

# 文件服务地址
export FILE_SERVICE_URL=http://localhost:8001

# 测试超时时间（秒）
export TEST_TIMEOUT=30

# 日志级别
export LOG_LEVEL=INFO
```

### 并发测试
如需测试并发性能，可以修改测试脚本，使用 `asyncio.gather()` 并行运行多个测试：

```python
# 并发插入测试示例
tasks = [
    insert_document(doc1),
    insert_document(doc2), 
    insert_document(doc3)
]
results = await asyncio.gather(*tasks)
```

## 📖 相关文档

- [STP项目开发规范](../规范文档.md)
- [LightRAG集成说明](../src/modules/lightraglocal/LIGHTRAG_INTEGRATION.md)
- [API接口文档](../src/modules/lightraglocal/README.md)

---

如有任何问题，请查看项目文档或联系开发团队。 