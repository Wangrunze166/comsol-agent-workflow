# 官方接口依据与版本边界

核验日期：2026-11-04。以下为官方文档核验，不代表本机求解、Java 编译或三个客户端加载已经实测通过。执行器针对 **COMSOL Multiphysics® 6.3 / Windows**；离线校验可在其他平台运行。

## COMSOL 6.3

| 官方来源 | 本项目采用的依据 |
|---|---|
| [Windows commands](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_ref_running.38.31.html) | 启动器在安装目录 `bin/win64`；Java 源先由 `comsolcompile` 编译，再将 `.class` 交给 `comsolbatch`。明确设置输出文件，防止默认覆盖 MPH 输入。`-batchlog` 留存日志，`-np` 控制核心数。 |
| [Programming Reference Manual](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/COMSOL_ProgrammingReferenceManual.pdf) | Windows 注册表 `HKLM\SOFTWARE\COMSOL\COMSOL63` 的 `COMSOLROOT` 可用于定位安装；本项目也允许显式指定安装目录。 |
| [ModelUtil](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.15.html) | `getComsolVersion()` 获取运行版本；`loadCopy()` 加载模型副本并要求另指定首次保存路径；`showProgress(filename)` 留存进度。 |
| [Model](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.16.html) | `model.save(filename)` 保存 MPH。模型中相对路径可能依赖模型目录，外部 CAD、插值表及其他依赖须单独声明并验证。 |
| [Parameters](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.50.html) | `param().set` 设置含单位表达式；`varnames()` 枚举已有参数；`evaluate` 与 `evaluateUnit` 可用于后续 COMSOL 内部核验。 |
| [Solver sequences](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.58.html) | `clearSolutionData()` 清理指定序列的旧解而保留配置；`runAll()` 运行该序列的全部特征；`isEmpty()` 检查是否存在解数据。单个序列不等于模型全部研究。 |
| [Studies](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_solver.51.58.html) | `study(tag).run()` 对应研究节点的 Compute。通用适配时需根据现有模型确定运行研究还是保留定制求解序列。 |
| [Solution dataset](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_results.52.149.html) | Solution 数据集用 `solution` 属性关联求解序列；后处理数据集必须指向本次产生的解。 |
| [EvalGlobal](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_results.52.049.html) | 全局数值结果可设置表达式与单位。`getReal()` 默认一行对应一个表达式，各列为解编号；复数结果另有 `getImag()` 和 `isComplex()`。 |
| [Data export](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_results.52.040.html) | 字段数据可通过已配置的 Data export 特征导出；不代表本 MVP 已自动建立任意模型的所有图片与场数据输出。 |

几何、材料、物理场、耦合与求解器的具体 feature 类型、属性名、选择集和表达式须以用户的 6.3 模型及其 Java 导出为准。不要将其他版本或其他物理接口的 API 片段直接当作已验证配置。静态单位检查只覆盖项目明确实现的单位集合，不能替代 COMSOL 的表达式检查或工程审查。

## 接口选择与许可边界

首选本机 Java / batch，避免把可选产品变成基础依赖。[官方 API 概述](https://www.comsol.com/support/learning-center/article/overview-of-the-comsol-api-107912)说明 Java API 可操作建模各阶段，LiveLink™ for MATLAB® 是另一种接入方式。采用 MATLAB 路线需要适用的 LiveLink 授权；将应用编译为独立程序与普通 Java 模型编译是不同功能。

本仓库许可证只针对原创编排代码、模板和说明。COMSOL 程序、运行库、许可文件、官方模型及客户资料不随仓库分发。对官方示例的修改、发布，以及商业应用或服务部署，需核对实际适用的 [6.3 软件许可协议](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_la_license.04.1.html)及示例随附条款。[官方应用发布说明](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/application_builder_introduction.08.010.html)列有部署方式；本项目不据此保证任何特定客户或账户的授权范围。

## Agent Skills 客户端

| 客户端 | 官方文档确认的项目目录 | 来源 |
|---|---|---|
| Codex | `.agents/skills/<name>/SKILL.md` | [Build skills](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code | `.claude/skills/<name>/SKILL.md` | [Extend Claude with skills](https://code.claude.com/docs/en/skills) |
| Cursor | `.cursor/skills/<name>/SKILL.md`，也读取 `.agents/skills/` | [Skills](https://cursor.com/help/customization/skills) |

共享 Skill 使用 `name`、`description` 元数据和 Markdown 指令。客户端专有扩展不作为执行前提；多个目录同时放置同名 Skill 可能重复发现，安装时选择目标客户端即可。这些是文档确认的兼容路径，实际发现与调用结果需在各客户端留存证据。
