# 官方接口依据与版本边界

核验日期：2026-11-04；源码版本 0.2.0。下面区分官方 API 依据和本项目的使用方式，不把文档存在当成本机求解验证。执行器针对 **COMSOL 6.3 / Windows**；离线工具可跨平台。实际完成状态见[验证记录](validation-status.md)。

## COMSOL 6.3

| 官方来源 | 本项目采用的依据 |
| --- | --- |
| [Windows commands](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_ref_running.38.31.html) | comsolcompile 编译 Java，comsolbatch 执行 class；batchlog/np 留存日志与限定核心数。smoke 使用独立驱动和 nosave；求解启用 autosave/recoverydir。 |
| [ModelUtil](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/api/com/comsol/model/util/ModelUtil.html) | getComsolVersion、loadCopy、showProgress；getRecoveryDir 获取实际模型恢复目录，loadRecovery 从恢复目录加载。 |
| [Model](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.16.html) | model.save 保存 MPH。相对模型资源可能依赖原目录，CAD／插值表等须声明和指纹绑定。 |
| [Parameters](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.50.html) | varnames 枚举已有参数，set 写含单位表达式，evaluate/evaluateUnit 用于 COMSOL 内部求值。 |
| [PropFeature](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/api/com/comsol/model/PropFeature.html) | properties/getValueType 和相应读取接口用于原生属性清单；未知类型或读取失败不能解释为无依赖。 |
| [SolverSequence](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/api/com/comsol/model/SolverSequence.html) | 新求解 clearSolutionData 后 runAll；isEmpty 检查解数据。恢复调用 continueRun，不清理恢复状态或静默改为 runAll。 |
| [Advanced](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_solver.51.17.html) | recoverysaveforce=manual、recoverysaveevery 为秒数、recoverysavinginfo=oneveryiteration。项目将可配置间隔限制为整数 1..3600。 |
| [Studies](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.60.html) | showAutoSequences 可生成默认序列；研究运行与生成配置分开。纯构建示例不调用 study.run 或 sol.runAll。 |
| [Solution dataset](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_results.52.149.html) | solution 属性关联求解序列，后处理必须绑定审阅的数据集。 |
| [EvalGlobal](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_results.52.049.html) | 表达式和单位控制全局评估；getReal 的行对应表达式，列对应解编号；复数结果需另处理，本 MVP 拒绝。 |
| [Results and tables](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.54.html) | 表格创建、setTableData、setColumnHeaders 与读回，用于带单位的全局结果表。 |
| [Image export](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_results.52.070.html) | 指定既有 plotgroup、PNG 类型和 pngfilename，保存实际场图；不自动配置任意物理场绘图。 |
| [Installation security settings](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_installation.02.012.html) | COMSOL 限制 Java 文件／系统访问；本项目保持原安全策略，普通数据经 stdout 交宿主受控落盘，模型与图片使用原生接口。 |

本机 getComsolVersion 实际返回带产品名和本地化补丁说明的字符串，执行器按有边界的 6.3 版本字段识别。退出码 0 不能证明 Java 操作成功；token、产物和数值检查共同构成执行证据。

scope 检查读取实际几何／网格／选择属性及参数表达式，并追踪传递引用。无法读取或不支持的间接表达式阻断不能安全判断的覆盖。这不等于支持全部 COMSOL 表达式，也不能替代边界覆盖、材料适用性或物理正确性审查。

## 独立加载、恢复和输出

smoke/dry-run 使用独立 SmokeDriver，仅加载和检查，不运行研究、重建网格、清空解或保存 MPH。恢复计划绑定实际恢复文件快照，使用 loadRecovery/continueRun；缺失状态拒绝续算，重新开始必须另建明确的新求解计划。

指标、表格、检查清单和恢复路径经带当前运行 token 的 stdout 载荷传递。宿主只接收计划允许的类型并选择输出文件名；不以关闭安全限制来获取普通 Java 文件访问。PNG/MPH 仍由 COMSOL 原生接口生成。文件可读和导出成功不等于工程验证通过。

## 审批接口与用户入口

v0.2 使用 [cryptography Ed25519](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/) 验签；用户持有加密私钥，执行端持受保护公钥。签名涵盖计划、动作、阶段和上游假设收据，手写 JSON 不授权运行。

[human-review.ps1](../scripts/human-review.ps1) 是供用户自行在可信交互终端执行的新求解入口，不应由 Agent 代运行签名步骤。TTY 仅约束交互，不是身份边界。密钥托管、受信公钥与执行器保护条件见[审批安全说明](approval-security.md)。

## 接口选择与许可边界

首选本机 Java/batch。[官方 API 概述](https://www.comsol.com/support/learning-center/article/overview-of-the-comsol-api-107912)介绍建模 API；LiveLink for MATLAB 是另一条需要相应许可的接入路线。普通 Java 模型编译不同于将应用编译为独立软件。

本仓库 MIT 许可只涵盖原创代码、模板和说明。COMSOL 软件、运行库、许可文件、官方模型和客户材料不随仓库分发。适用范围以[6.3 软件许可协议](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_la_license.04.1.html)和具体条款为准；本项目不承诺某个账户或部署天然具有授权。

## Agent Skills 客户端

| 客户端 | 文档确认的项目目录 | 来源 |
| --- | --- | --- |
| Codex | .agents/skills/&lt;name&gt;/SKILL.md | [Build skills](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code | .claude/skills/&lt;name&gt;/SKILL.md | [Extend Claude with skills](https://code.claude.com/docs/en/skills) |
| Cursor | .cursor/skills/&lt;name&gt;/SKILL.md，也读取 .agents/skills/ | [Skills](https://cursor.com/help/customization/skills) |

共享 Skill 使用 name、description 元数据和 Markdown 指令。多个发现目录可能造成重复，安装时选择目标客户端。文档确认的目录兼容性与三个客户端的真实加载证据分别记录。
