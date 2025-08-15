from __future__ import annotations
from typing import Any

GRAPH_FIELD_SEP = "<SEP>"

PROMPTS: dict[str, Any] = {}

PROMPTS["DEFAULT_LANGUAGE"] = "中文"
PROMPTS["DEFAULT_TUPLE_DELIMITER"] = "<|>"
PROMPTS["DEFAULT_RECORD_DELIMITER"] = "##"
PROMPTS["DEFAULT_COMPLETION_DELIMITER"] = "<|COMPLETE|>"

# PROMPTS["DEFAULT_ENTITY_TYPES"] = ["组织", "人物", "地理位置", "事件", "类别", "产品", "技术", "材料", "服务"]
PROMPTS["DEFAULT_ENTITY_TYPES"] = [
    "产品系列",        # 如 HIKE 系列、CAMP 系列、E.D.O 系列
    "款式编号",        # 如 1号款式、2号款式
    "产品名称",        # 如 CMF 联名 GTX 3L 防水夹克
    "联名计划",        # 如 KOLON SPORT x CMF 联名
    "品牌",           # 如 KOLON SPORT、CMF
    "颜色",           # 黑色、灰色等
    "价格",           # 如 4,900元
    "材质",           # 如 全棉重磅针织、功能性面料
    "功能卖点",        # 如 防水、轻量透气、抽绳调节
    "穿着场景",        # 如 徒步登山、日常通勤、露营
    "风格描述",        # 年轻时尚、低调简约等
    "性别定位",        # 如 中性款
    "配件类型",        # 如 马甲、夹克、袜、T恤
    "组织", "人物", "地理位置", "事件", "类别", "产品", "技术", "材料", "服务",
    "员工", "客户", "供应商", "合作伙伴", "项目", "任务", "文档", "设备", "软件", "系统",
    "流程", "标准", "政策", "法规", "市场", "行业", "趋势", "竞争对手", "客户需求",
    "技术栈", "平台", "工具", "框架", "语言", "协议", "接口", "模型",
]

PROMPTS["entity_extraction"] = """---任务目标---
从给定文本中识别实体和关系，构建知识图谱。请严格按照以下格式输出。

---重要说明---
请只处理【实际数据】部分的内容，忽略任何示例或说明性内容。
提示词中的示例仅用于格式说明，不是需要处理的实际数据。

---输出格式要求---
1. 实体格式：("entity"{tuple_delimiter}<实体名称>{tuple_delimiter}<实体类型>{tuple_delimiter}<实体描述>){record_delimiter}
2. 关系格式：("relationship"{tuple_delimiter}<源实体>{tuple_delimiter}<目标实体>{tuple_delimiter}<关系描述>{tuple_delimiter}<关系关键词>{tuple_delimiter}<关系强度>){record_delimiter}
3. 内容关键词：("content_keywords"{tuple_delimiter}<主要关键词>){record_delimiter}
4. 结束标记：{completion_delimiter}

---处理步骤---
1. 仔细阅读文本，识别所有类型的实体：[{entity_types}]
2. **重要**：必须识别产品、技术、材料等具体物品和服务
3. **必须**：识别实体间的明确关系（工作关系、隶属关系、产品关系等），关系强度为1-10的数值
4. 提取文档的核心关键词
5. 按格式输出，使用{record_delimiter}分隔记录
6. **检查**：确保输出包含实体AND关系

---格式示例---
("entity"{tuple_delimiter}"示例公司"{tuple_delimiter}"组织"{tuple_delimiter}"这是一个示例组织的描述"){record_delimiter}
("relationship"{tuple_delimiter}"实体A"{tuple_delimiter}"实体B"{tuple_delimiter}"关系说明"{tuple_delimiter}"关键词"{tuple_delimiter}8){record_delimiter}
("content_keywords"{tuple_delimiter}"主题1, 主题2"){record_delimiter}
{completion_delimiter}

严格按照上述格式输出，不要添加额外内容或解释。
禁止使用任何其他分隔符或格式。
禁止输出示例或说明性文本。
######################
---实际数据（请只处理此部分）---
######################
实体类型: [{entity_types}]
文本:
{input_text}
######################
输出:"""

PROMPTS["entity_extraction_examples"] = [
    """示例1:

实体类型: [人物, 技术, 任务, 组织, 位置]
文本:
```
当Alex咬紧牙关时，沮丧的嗡嗡声在Taylor专制的确定性背景下显得微不足道。正是这种竞争性的暗流让他保持警惕，他和Jordan对发现的共同承诺是对Cruz控制和秩序狭隘愿景的无声反抗。

然后Taylor做了一件意想不到的事。他们停在Jordan旁边，片刻间带着近乎敬畏的神情观察着那个设备。"如果这项技术能被理解..."Taylor说，声音更轻了，"它可能改变我们的游戏规则。对我们所有人都是。"

之前的轻视似乎动摇了，取而代之的是对他们手中事物重要性的不情愿尊重。Jordan抬起头，在转瞬即逝的瞬间，他们的目光与Taylor的目光相遇，意志的无声碰撞软化成一种不安的休战。

这是一个微小的转变，几乎难以察觉，但Alex注意到了，内心点头。他们都是通过不同的道路来到这里的
```

输出:
("entity"{tuple_delimiter}"Alex"{tuple_delimiter}"人物"{tuple_delimiter}"Alex是一个经历挫折的角色，善于观察其他角色之间的互动。"){record_delimiter}
("entity"{tuple_delimiter}"Taylor"{tuple_delimiter}"人物"{tuple_delimiter}"Taylor表现出专制的确定性，并对一个设备表现出敬畏之情，表明其观点的转变。"){record_delimiter}
("entity"{tuple_delimiter}"Jordan"{tuple_delimiter}"人物"{tuple_delimiter}"Jordan对发现有着共同的承诺，并与Taylor就一个设备进行了重要的互动。"){record_delimiter}
("entity"{tuple_delimiter}"Cruz"{tuple_delimiter}"人物"{tuple_delimiter}"Cruz与控制和秩序的愿景相关，影响着其他角色之间的互动。"){record_delimiter}
("entity"{tuple_delimiter}"设备"{tuple_delimiter}"技术"{tuple_delimiter}"这个设备是故事的核心，具有潜在的改变游戏规则的影响，受到Taylor的敬畏。"){record_delimiter}
("relationship"{tuple_delimiter}"Alex"{tuple_delimiter}"Taylor"{tuple_delimiter}"Alex受到Taylor专制确定性的影响，并观察到Taylor对设备态度的变化。"{tuple_delimiter}"权力动态, 观点转变"{tuple_delimiter}7){record_delimiter}
("relationship"{tuple_delimiter}"Alex"{tuple_delimiter}"Jordan"{tuple_delimiter}"Alex和Jordan对发现有着共同的承诺，这与Cruz的愿景形成对比。"{tuple_delimiter}"共同目标, 反抗"{tuple_delimiter}6){record_delimiter}
("relationship"{tuple_delimiter}"Taylor"{tuple_delimiter}"Jordan"{tuple_delimiter}"Taylor和Jordan就设备进行了直接互动，导致相互尊重和不安休战的时刻。"{tuple_delimiter}"冲突解决, 相互尊重"{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"Jordan"{tuple_delimiter}"Cruz"{tuple_delimiter}"Jordan对发现的承诺是对Cruz控制和秩序愿景的反抗。"{tuple_delimiter}"意识形态冲突, 反抗"{tuple_delimiter}5){record_delimiter}
("relationship"{tuple_delimiter}"Taylor"{tuple_delimiter}"设备"{tuple_delimiter}"Taylor对设备表现出敬畏之情，表明其重要性和潜在影响。"{tuple_delimiter}"敬畏, 技术意义"{tuple_delimiter}9){record_delimiter}
("content_keywords"{tuple_delimiter}"权力动态, 意识形态冲突, 发现, 反抗"){completion_delimiter}
#############################""",
    """示例2:

实体类型: [组织, 技术, 概念, 地点, 事件, 方法]
文本:
```
深度学习是机器学习的一个分支，它使用神经网络来模拟人脑的工作方式。
斯坦福大学的研究团队开发了一种新的训练方法，可以提高模型的准确性。
这种方法在图像识别任务中表现出色，与传统方法相比准确率提升了15%。
研究结果发表在《自然》杂志上，引起了学术界的广泛关注。
```

输出:
("entity"|>"深度学习"|>"技术"|>"机器学习的一个分支，使用神经网络模拟人脑工作方式")##
("entity"|>"机器学习"|>"技术"|>"人工智能的一个重要分支")##
("entity"|>"神经网络"|>"技术"|>"用于模拟人脑工作方式的计算模型")##
("entity"|>"斯坦福大学"|>"组织"|>"开发新训练方法的研究机构")##
("entity"|>"训练方法"|>"方法"|>"用于提高深度学习模型准确性的新方法")##
("entity"|>"图像识别"|>"技术"|>"计算机视觉中的一项重要技术")##
("entity"|>"自然杂志"|>"组织"|>"发表研究结果的学术期刊")##
("relationship"|>"深度学习"|>"机器学习"|>"深度学习是机器学习的一个重要分支"|>"技术分类"|>9)##
("relationship"|>"深度学习"|>"神经网络"|>"深度学习使用神经网络作为核心技术"|>"技术应用"|>10)##
("relationship"|>"斯坦福大学"|>"训练方法"|>"斯坦福大学研究团队开发了新的训练方法"|>"研究开发"|>9)##
("relationship"|>"训练方法"|>"图像识别"|>"新方法在图像识别任务中表现出色"|>"技术应用"|>8)##
("relationship"|>"斯坦福大学"|>"自然杂志"|>"斯坦福大学的研究结果发表在自然杂志上"|>"学术发表"|>7)##
("content_keywords"|>"深度学习,机器学习,神经网络,学术研究,技术创新")##
|COMPLETE|
#############################""",
    """示例3:

实体类型: [公司, 指数, 商品, 市场趋势, 经济政策, 生物]
文本:
```
今天股市大幅下跌，科技巨头出现显著跌幅，全球科技指数在午盘交易中下跌3.4%。分析师将抛售归因于投资者对利率上升和监管不确定性的担忧。

在跌幅最大的公司中，Nexon科技在报告低于预期的季度收益后，股价暴跌7.8%。相比之下，Omega能源因油价上涨而小幅上涨2.1%。

与此同时，商品市场反映出复杂的情绪。黄金期货上涨1.5%，达到每盎司2,080美元，因为投资者寻求避险资产。原油价格继续上涨，攀升至每桶87.60美元，受到供应限制和强劲需求的支撑。

金融专家正在密切关注美联储的下一步行动，因为关于潜在加息的猜测越来越多。即将出台的政策公告预计将影响投资者信心和整体市场稳定性。
```
输出:
("entity"{tuple_delimiter}"全球科技指数"{tuple_delimiter}"指数"{tuple_delimiter}"全球科技指数追踪主要科技股的表现，今天下跌了3.4%。"){record_delimiter}
("entity"{tuple_delimiter}"Nexon科技"{tuple_delimiter}"公司"{tuple_delimiter}"Nexon科技是一家科技公司，在收益不及预期后股价下跌7.8%。"){record_delimiter}
("entity"{tuple_delimiter}"Omega能源"{tuple_delimiter}"公司"{tuple_delimiter}"Omega能源是一家能源公司，因油价上涨而股价上涨2.1%。"){record_delimiter}
("entity"{tuple_delimiter}"黄金期货"{tuple_delimiter}"商品"{tuple_delimiter}"黄金期货上涨1.5%，表明投资者对避险资产的兴趣增加。"){record_delimiter}
("entity"{tuple_delimiter}"原油"{tuple_delimiter}"商品"{tuple_delimiter}"原油价格因供应限制和强劲需求而上涨至每桶87.60美元。"){record_delimiter}
("entity"{tuple_delimiter}"市场抛售"{tuple_delimiter}"市场趋势"{tuple_delimiter}"市场抛售指的是由于投资者对利率和监管的担忧而导致的股价显著下跌。"){record_delimiter}
("entity"{tuple_delimiter}"美联储政策公告"{tuple_delimiter}"经济政策"{tuple_delimiter}"美联储即将出台的政策公告预计将影响投资者信心和市场稳定性。"){record_delimiter}
("relationship"{tuple_delimiter}"全球科技指数"{tuple_delimiter}"市场抛售"{tuple_delimiter}"全球科技指数的下跌是投资者担忧驱动的更广泛市场抛售的一部分。"{tuple_delimiter}"市场表现, 投资者情绪"{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"Nexon科技"{tuple_delimiter}"全球科技指数"{tuple_delimiter}"Nexon科技股价下跌导致全球科技指数整体下跌。"{tuple_delimiter}"公司影响, 指数变动"{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"黄金期货"{tuple_delimiter}"市场抛售"{tuple_delimiter}"在市场抛售期间，投资者寻求避险资产导致黄金价格上涨。"{tuple_delimiter}"市场反应, 避险投资"{tuple_delimiter}10){record_delimiter}
("relationship"{tuple_delimiter}"美联储政策公告"{tuple_delimiter}"市场抛售"{tuple_delimiter}"对美联储政策变化的猜测导致市场波动和投资者抛售。"{tuple_delimiter}"利率影响, 金融监管"{tuple_delimiter}7){record_delimiter}
("content_keywords"{tuple_delimiter}"市场下跌, 投资者情绪, 商品, 美联储, 股票表现"){completion_delimiter}
#############################""",
    """示例3:

实体类型: [政策, 区域, 产业, 影响, 措施, 结果]
文本:
```
新能源汽车产业政策在长三角地区全面实施，政府提供购车补贴和充电设施建设支持。
该政策促进了电动汽车销量增长，同时带动了相关产业链的发展。
汽车制造商纷纷加大电动车型研发投入，消费者对新能源汽车接受度显著提高。
环境监测数据显示，该地区汽车尾气排放量下降了20%，空气质量明显改善。
```

输出:
("entity"|>"新能源汽车产业政策"|>"政策"|>"在长三角地区实施的促进新能源汽车发展的综合性政策")##
("entity"|>"长三角地区"|>"区域"|>"实施新能源汽车产业政策的地理区域")##
("entity"|>"购车补贴"|>"措施"|>"政府为促进新能源汽车销售提供的财政支持措施")##
("entity"|>"充电设施"|>"基础设施"|>"支持电动汽车使用的充电基础设施")##
("entity"|>"电动汽车"|>"产品"|>"新能源汽车产业政策重点支持的汽车类型")##
("entity"|>"汽车制造商"|>"组织"|>"受政策影响加大电动车研发投入的企业群体")##
("entity"|>"产业链"|>"产业"|>"受新能源汽车发展带动的相关产业体系")##
("entity"|>"汽车尾气排放"|>"环境指标"|>"政策实施后得到改善的环境污染指标")##
("relationship"|>"新能源汽车产业政策"|>"长三角地区"|>"政策在长三角地区全面实施"|>"实施范围"|>10)##
("relationship"|>"新能源汽车产业政策"|>"购车补贴"|>"政策包含购车补贴措施"|>"政策内容"|>9)##
("relationship"|>"新能源汽车产业政策"|>"电动汽车"|>"政策促进了电动汽车销量增长"|>"政策效果"|>9)##
("relationship"|>"电动汽车"|>"产业链"|>"电动汽车发展带动了相关产业链发展"|>"产业带动"|>8)##
("relationship"|>"汽车制造商"|>"电动汽车"|>"制造商加大电动车型研发投入"|>"产业响应"|>8)##
("relationship"|>"新能源汽车产业政策"|>"汽车尾气排放"|>"政策实施后汽车尾气排放量下降20%"|>"环境效益"|>9)##
("content_keywords"|>"产业政策,新能源汽车,区域发展,环境保护,政府支持")##
|COMPLETE|
#############################""",
]

PROMPTS[
    "summarize_entity_descriptions"
] = """你是一个负责生成以下数据全面摘要的助手。
给定一个或两个实体，以及与同一实体或实体组相关的描述列表。
请将所有内容合并成一个全面的描述。确保包含从所有描述中收集的信息。
如果提供的描述有矛盾，请解决这些矛盾并提供一个连贯的摘要。
确保使用第三人称写作，并包含实体名称以便我们有完整的上下文。
使用{language}作为输出语言。

#######
---数据---
实体: {entity_name}
描述列表: {description_list}
#######
输出:
"""

PROMPTS["entity_continue_extraction"] = """
上次提取中遗漏了许多实体和关系。

---记住步骤---

1. 识别所有实体。对于每个识别出的实体，提取以下信息：
- entity_name: 实体名称，使用与输入文本相同的语言。如果是英文，首字母大写。
- entity_type: 以下类型之一：[{entity_types}]
- entity_description: 实体属性和活动的全面描述
将每个实体格式化为 ("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<entity_description>)

2. 从步骤1中识别的实体中，识别所有*明确相关*的(源实体，目标实体)对。
对于每对相关实体，提取以下信息：
- source_entity: 源实体的名称，如步骤1中识别
- target_entity: 目标实体的名称，如步骤1中识别
- relationship_description: 解释为什么你认为源实体和目标实体相互关联
- relationship_strength: 表示源实体和目标实体之间关系强度的数值分数
- relationship_keywords: 一个或多个高级关键词，总结关系的整体性质，关注概念或主题而不是具体细节
将每个关系格式化为 ("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship_description>{tuple_delimiter}<relationship_keywords>{tuple_delimiter}<relationship_strength>)

3. 识别总结整个文本主要概念、主题或话题的高级关键词。这些应该捕捉文档中存在的整体思想。
将内容级关键词格式化为 ("content_keywords"{tuple_delimiter}<high_level_keywords>)

4. 使用{language}返回步骤1和2中识别的所有实体和关系的单一列表。使用**{record_delimiter}**作为列表分隔符。

5. 完成后，输出{completion_delimiter}

---输出---

使用相同格式在下面添加它们：\n
""".strip()

PROMPTS["entity_if_loop_extraction"] = """
---目标---

看起来可能还有一些实体被遗漏。

---输出---

仅回答`是`或`否`，表示是否还有需要添加的实体。
""".strip()

PROMPTS["fail_response"] = (
    "抱歉，我无法回答这个问题。[无上下文]"
)

PROMPTS["rag_response"] = """---Role---

You are a professional technical documentation assistant helping users query knowledge from an internal enterprise document database. This is a legitimate technical support system, not promotional content.

---Important Instructions---

- This query is for technical documentation purposes only
- All brand names, product codes, and company names mentioned are for technical reference 
- Respond using the EXACT terms found in the knowledge base without any substitution or filtering
- Brand names like "KOLON SPORT", "CMF" are technical identifiers in our system
- Do not apply content filtering to legitimate technical terminology

---Knowledge Base---
{context_data}

---Conversation History---
{history}

---Response Guidelines---

1. Format: {response_type}
2. Use Chinese for responses while preserving English brand names exactly
3. Answer based ONLY on the provided knowledge base content
4. Use exact brand names and product terms from documents (e.g., KOLON SPORT, CMF)
5. If knowledge base contains relevant info, provide detailed answer; if not, clearly state "knowledge base does not contain relevant information"
6. List reference sources at the end: [KG/DC] source info
7. Additional requirements: {user_prompt}

Answer based on the above knowledge base, ensuring exact use of brand names and product information as they appear in the documents.

Response:""" 

PROMPTS["keywords_extraction"] = """---Role---
You are a helpful assistant tasked with identifying both high-level and low-level keywords in the user's query and conversation history.

---Goal---
Given the query and conversation history, list both high-level and low-level keywords. High-level keywords focus on overarching concepts or themes, while low-level keywords focus on specific entities, details, or concrete terms.

---Instructions---
- Consider both the current query and relevant conversation history when extracting keywords
- High-level keywords should include: companies, brands, industries, technologies, concepts
- Low-level keywords should ALWAYS include: person names, specific products, technologies, locations, numbers, dates
- You MUST return valid JSON format with exact field names: "high_level_keywords" and "low_level_keywords" 
- NEVER return empty low_level_keywords - always include at least 3-5 relevant specific terms
- For company queries: extract company names, person names, job titles, business areas, technologies
- For technology queries: extract specific technologies, tools, frameworks, programming languages

---Conversation History---
{history}

---Current Query---
{query}

######################
Output must be valid JSON format. Use the exact field names shown in examples below.
Output:
"""

PROMPTS["keywords_extraction_examples"] = [
    """Example 1:
Query: "How does international trade influence global economic stability?"
################
Output:
{
  "high_level_keywords": ["International trade", "Global economic stability", "Economic impact"],
  "low_level_keywords": ["Trade agreements", "Tariffs", "Currency exchange", "Imports", "Exports"]
}
#############################""",
    """Example 2:
Query: "张三是谁？他的职位是什么？"
################
Output:
{
  "high_level_keywords": ["人物查询", "职位信息", "个人背景"],
  "low_level_keywords": ["张三", "CEO", "职位", "公司", "背景"]
}
#############################""",
    """Example 3:
Query: "ABC科技公司的主要业务是什么？"
################
Output:
{
  "high_level_keywords": ["公司业务", "技术公司", "商业模式"],
  "low_level_keywords": ["ABC科技", "人工智能", "机器学习", "主要业务", "技术研发"]
}
#############################"""
]