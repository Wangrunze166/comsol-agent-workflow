# COMSOL Agent Workflow

![COMSOL Agent Workflow：从经审阅模型到可复现运行](assets/hero.svg)

[![Offline checks](https://github.com/Wangrunze166/comsol-agent-workflow/actions/workflows/check.yml/badge.svg)](https://github.com/Wangrunze166/comsol-agent-workflow/actions/workflows/check.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-087e8b.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3273ba.svg)](pyproject.toml)
[![COMSOL 6.3](https://img.shields.io/badge/COMSOL-6.3-a85b10.svg)](adapters/comsol63/README.md)

**中文** · [English](README.en.md) · [快速开始](#快速开始) · [演示](docs/demonstration.md) · [验证记录](docs/validation-status.md)

**面向 Codex、Claude Code 和 Cursor 的 COMSOL 工程工作流：审阅模型，检查输入，人类签名批准，计算并交付证据。**

将已有 MPH、参数单位、工程假设、求解日志和验证报告组织成可复现项目。通用 Agent Skill 负责工程流程，独立执行器适配 COMSOL 6.3。当前范围是已审阅模型的参数化复算；新几何、新物理场和新领域通过专门的建模器或审阅后的 MPH 接入。

**v0.2：最小导热板已在本机构建；只加载检查、几何/网格参数阻断和错误标签阻断均已实测通过。真实求解正在等待用户签署，尚无完整求解成功证据。**

## v0.2 做什么

| 环节 | 行为 |
| --- | --- |
| 输入检查 | 检查参数单位、量纲、范围、模型来源和预期结果坐标 |
| 加载预检 | `smoke` / `dry-run` 只加载并检查模型标签与引用，不求解、不保存新 MPH |
| 参数作用范围 | Java API 读取几何／网格属性与参数表达式，追踪直接及间接引用；命中时阻断标成 `physics_scalar` 的覆盖 |
| 人类审批 | 独立 `approve` 命令生成 Ed25519 签名收据；分别绑定工程假设和求解／恢复动作 |
| 执行与诊断 | 保留启动器和 COMSOL 日志、运行标记、指标 CSV、新 MPH 与报告；退出码 0 不能单独判成功 |
| 中断恢复 | 从实际 recovery 数据建立新计划，通过 `loadRecovery` / `continueRun` 续算；不静默退回从头运行 |
| 后处理 | 全局实数指标；可选导出已配置场图 PNG 和含单位的结果表格 |

审批的安全边界来自**用户控制的签名密钥、受保护的公钥和执行器**。TTY 只约束交互方式，不能证明操作者是人。私钥和口令必须位于 Agent 无权访问的边界外；共享管理员权限的单机环境不能由一个脚本保证不可绕过。见[审批安全说明](docs/approval-security.md)。

## 架构

![六个阶段：模型来源、计划检查、工程确认、求解审批、COMSOL执行、验证报告](assets/workflow.svg)

| 层次 | 职责 | 入口 |
| --- | --- | --- |
| 通用 Skill | 恢复工程证据，组织假设审阅、诊断和验证 | [SKILL.md](skills/comsol-multiphysics/SKILL.md) |
| 案例与计划 | 参数、单位、验收标准、输入指纹、签名审批绑定 | [案例格式](docs/case-format.md) |
| COMSOL 6.3 执行器 | 本机加载检查、已审阅序列执行、恢复和导出 | [适配器](adapters/comsol63/README.md) |

模型或执行代码变化后重新生成计划和签名。求解完成后，守恒、网格、时间步和实验一致性仍需分别验证。

## 快速开始

离线规划和 CSV 比较只需 Python 3.10+；签名审批使用可选的 `cryptography` 依赖。

```console
git clone https://github.com/Wangrunze166/comsol-agent-workflow.git
cd comsol-agent-workflow
python -m comsol_workflow --help
python -m comsol_workflow compare examples/offline/actual.csv examples/offline/reference.csv --coordinate time_s --atol 0.01 --rtol 0.001
python -m comsol_workflow plan examples/minimal-heat-plate/case.json --out runs/first-review
```

比较输入是合成测试数据。公开仓库不附 MPH，最后一条命令会生成 `REVIEW.md` 并列出缺失模型、安装路径等条件；它不启动求解，也不生成已批准收据。每次规划使用新的空目录。

开发检查与签名依赖：

```console
python -m pip install -e ".[approval]"
python -m unittest discover -s tests -v
```

真实执行需要 Windows、COMSOL 6.3、相应模块的有效许可、已审阅 MPH 和用户签名审批。按[完整演示](docs/demonstration.md)先做只加载检查，再由用户确认假设并批准求解。

## 最小示例：稳态导热板

[minimal-heat-plate](examples/minimal-heat-plate/README.md) 提供 Java 建模器和案例配置：10 × 5 mm 二维板，左侧 293.15 K、右侧 303.15 K，上下绝热，无内热源。解析平均温度为 **298.15 K**。

构建器按坐标选择边界，配置材料、网格、研究和结果节点，只保存未求解模型。本机已核验左右各一个边界、192 个网格单元以及空解状态。这个新例子用于验证执行链，不代替原有多物理场研究，也不能据此宣称完成求解或达到 5 分钟耗时目标。

## 工程参考案例：热电模块与 PI 控制

![热电案例概念示意：稳态流场、热网络与PI反馈](assets/thermoelectric-case.svg)

保留 [COMSOL 官方案例 102421](https://www.comsol.com/model/lumped-thermoelectric-module-with-pid-control-102421) 的两个复现清单：稳态 0.5–3.5 A 电流扫描，共 7 点；瞬态 0–60 min 温控，共 31 个输出时刻。该配置先求稳态流场，再固定流场计算热学；微分增益为零，实际采用 PI 控制。

以上图片为原创概念示意，不是计算场图。官方模型由使用者按许可获取，历史计算记录与本执行器的验证证据分开保留。

## 证据矩阵

| 项目 | 当前边界 |
| --- | --- |
| 离线测试与 CI | 最新结果见测试工作流和[验证记录](docs/validation-status.md)；不等于 COMSOL 运行成功 |
| 最小模型 Java 编译与构建 | 本机 COMSOL 6.3.0.290 已通过；保存时 `sol1.isEmpty=true` |
| 新执行器 load-only smoke | 本机通过，含编译27.37秒；几何/网格参数覆盖和错误研究标签均被阻断 |
| 签名审批、引用阻断、恢复、可选导出 | 已实现；各项离线／本机证据分别记录，不能统称全部实测通过 |
| 完整真实求解与数值基准 | **尚未完成** |
| 网格、守恒、时间步、实验验证 | **尚未完成** |
| Codex／Claude Code／Cursor | 共享 Skill 和项目入口；三个客户端的原生加载未全部实测 |

## 在 AI 编程工具中使用

选择客户端，把共享 Skill 复制到本项目的发现目录：

```console
python scripts/install_skill.py --client codex --project .
```

`--client` 也支持 `claude`、`cursor`，已有同名 Skill 不会被覆盖。仓库提供 `AGENTS.md`、`CLAUDE.md` 和 Cursor 规则。可让助手先恢复模型证据、准备案例和计划、执行只加载检查；签名由用户在受信环境完成。

## 文档与定制

- [完整流程](docs/workflow.md) · [案例格式](docs/case-format.md) · [接口依据](docs/interface-sources.md)
- [建模审阅模板](templates/model-configuration.template.md) · [工程验证模板](templates/verification-plan.template.md)
- [贡献指南](CONTRIBUTING.md) · [问题与需求](https://github.com/Wangrunze166/comsol-agent-workflow/issues/new/choose) · [发布步骤](docs/release.md)
- [定制开发范围](docs/commercialization.md)：客户模型接入、领域建模器、求解诊断、团队部署和验证报告；以具体模型族及验收指标约定交付。

介绍与工程组织方式参考 **FreeCAD、Taichi、MuJoCo、Open3D**，四者均在 2026-11-04 通过 GitHub API 核验超过 10K stars。[星数与源码依据](docs/high-star-engineering-references.md) · [图文参考](docs/presentation-references.md)。图文均为本项目原创。

## 许可

原创代码、Skill、模板和示意图采用 [MIT](LICENSE)。COMSOL 软件、模块、商标、官方模型及客户资料保留各自权利，不随本仓库分发。本项目独立维护，不代表 COMSOL 官方。
