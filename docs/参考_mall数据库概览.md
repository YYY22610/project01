# mall 数据库表结构概览（参考范例：macrozheng/mall）

> 来源：https://www.macrozheng.com/mall/database/mall_database_overview.html
> 用途：真实电商项目的数据库说明组织方式范本。特点是**按业务模块分组**，每组配「数据库表结构图 + 功能结构图」。可对照本项目《数据库说明书》把 10 张表从「平铺」改为「按模块（参与者 / 行为 / 问卷 / 评分）分组」。

## 页面组织方式

该页属于 mall 学习教程的「业务篇」，对后台五大模块做数据库表结构及功能概要介绍。页面注明：「部分功能暂未实现，只是对表结构进行了设计，商品管理、订单管理、营销管理大部分功能均已实现。」

按以下 5 个模块组织，每个模块均包含：
- **数据库表结构**（图示）
- **功能结构**（图示）

| 业务模块 | 数据库表结构图 | 功能结构图 |
|---------|---------------|-----------|
| 商品管理 | mall_pms | mall_func_pms |
| 订单管理 | mall_oms | mall_func_oms |
| 营销管理 | mall_sms | mall_func_sms |
| 内容管理 | mall_cms | mall_func_cms |
| 用户管理 | mall_ums | mall_func_ums |

> 原网页以图片展示各模块表结构，具体表名（如 `ums_admin`、`pms_product`、`oms_order`）需查看对应的 PowerDesigner 文件。

## 相关资料（可下载的详细设计文件）

**PowerDesigner 数据库设计文件**（.pdm，含完整表定义）：
- 商品管理：https://github.com/macrozheng/mall-learning/blob/master/document/pdm/mall_pms.pdm
- 订单管理：https://github.com/macrozheng/mall-learning/blob/master/document/pdm/mall_oms.pdm
- 营销管理：https://github.com/macrozheng/mall-learning/blob/master/document/pdm/mall_sms.pdm
- 内容管理：https://github.com/macrozheng/mall-learning/blob/master/document/pdm/mall_cms.pdm
- 用户管理：https://github.com/macrozheng/mall-learning/blob/master/document/pdm/mall_ums.pdm

**MindMaster 功能思维导图**（.emmx）：
- 商品管理：https://github.com/macrozheng/mall-learning/blob/master/document/mind/pms.emmx
- 订单管理：https://github.com/macrozheng/mall-learning/blob/master/document/mind/oms.emmx
- 营销管理：https://github.com/macrozheng/mall-learning/blob/master/document/mind/sms.emmx
- 内容管理：https://github.com/macrozheng/mall-learning/blob/master/document/mind/cms.emmx
- 用户管理：https://github.com/macrozheng/mall-learning/blob/master/document/mind/ums.emmx

使用工具：PowerDesigner（http://powerdesigner.de/）、MindMaster（http://www.edrawsoft.cn/mindmaster）

---

**对本书项目《数据库说明书》的借鉴点**：
- 把表从「按名称顺序平铺」改为**「按业务模块分组 + 模块功能说明」**（如：参与者与账户模块 / 行为与交互模块 / 问卷与测评模块 / 评分与管理模块）。
- 每个模块除了字段表，补一段「模块功能说明」，读起来更像设计说明而非数据字典。
