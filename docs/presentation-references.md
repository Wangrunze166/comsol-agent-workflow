# 项目介绍与配图参考

核验日期：**2026-11-04**。本轮参考项目全部满足 GitHub stars ≥10,000；下表为 API 当日快照。它们用于研究工程软件如何介绍用途、展示实例和组织文档，不是本项目依赖，也不构成合作或背书。具体实现依据见[高星工程源码参考](high-star-engineering-references.md)。

| 项目 | 当日 stars／核验 | 参考的公开介绍 | 本项目采用的方式 |
| --- | --- | --- | --- |
| [FreeCAD](https://github.com/FreeCAD/FreeCAD) | 35,115 · [API](https://api.github.com/repos/FreeCAD/FreeCAD) | README 的工程软件定位、项目形象和使用／开发入口 | 先说明面向哪些工具、哪些模型，再给安装和贡献入口；把建模职责与执行职责分开 |
| [Taichi](https://github.com/taichi-dev/taichi) | 28,454 · [API](https://api.github.com/repos/taichi-dev/taichi) | README 的简短定位、可运行示例与可视结果 | 提供一个可读的小型示例及解析基准；图片说明必须指出是示意还是实算 |
| [MuJoCo](https://github.com/google-deepmind/mujoco) | 16,056 · [API](https://api.github.com/repos/google-deepmind/mujoco) | README 集中说明模拟器用途、获取方式和文档入口 | 能力清单贴近可执行操作；加载、求解、恢复分别写明前提和证据 |
| [Open3D](https://github.com/isl-org/Open3D) | 14,173 · [API](https://api.github.com/repos/isl-org/Open3D) | README 的图形展示、功能入口与安装文档 | 保留原创架构图；只有实际场图导出完成并可追溯后才加入结果展示 |

## 介绍页结构

1. 一句话定位：Codex／Claude Code／Cursor 使用的 COMSOL 工程工作流。
2. 当前边界：v0.2 先描述实现，再列本机已验证、验证中和未验证内容。
3. 架构：共享 Skill、案例与计划、COMSOL 6.3 专属执行器。
4. 最短入口：无需 COMSOL 的离线体验，以及需要许可和真实审批的本机演示。
5. 最小模型：10 × 5 mm 导热板、解析平均温度 298.15 K、未求解构建证据。
6. 证据矩阵：离线测试、编译、加载、实际求解和工程验证分别列示。

## 图片与文字约定

- `assets/hero.svg`、`assets/workflow.svg`、`assets/thermoelectric-case.svg` 为本项目原创概念图，继续保留。配色区分组件和阶段，不解释为温度、应力或流速。
- 不复制参考项目的标识、图片、动画或计算结果，不借其星数或性能承诺暗示本项目已达到同等成熟度。
- 最小导热板本机已构建并保存为空解；构建日志中的耗时不能描述为求解耗时。
- 人类审批以用户签名密钥与受保护执行器为边界；TTY 只防止误用管道，不被写成人类身份认证。
- 真实场图需附案例配置、求解记录、单位和适用范围；图像导出成功仍不等于物理正确。
- 客户模型、许可证、私人机器路径和签名秘密不进入公开介绍。对外验证摘要应链接可审核证据。

当前能力与运行证据以[验证记录](validation-status.md)为准。参考项目星数仅代表核验日期的公开数据，后续可能变化。
