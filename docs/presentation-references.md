# 项目介绍与配图参考

查阅日期：2026-11-04。以下项目用于参考公开工程软件如何介绍能力、展示图形和引导使用；它们不是本项目的依赖，也不表示合作或背书。本仓库的介绍文案与示意图单独编写，不复制这些项目的标识、图集或仿真结果。

| 参考项目 | 实际查看的内容 | 本项目采用的表达方式 |
|---|---|---|
| [PyVista](https://github.com/pyvista/pyvista) | README 将简短定位、宽幅示例图集、快速开始和专业支持分开；[示例横幅](https://raw.githubusercontent.com/pyvista/pyvista/main/doc/source/_static/pyvista_banner_small.png) 以白底排列网格、切片、流线、曲面等视觉对象 | 用原创图形先说明对象和流程，再提供可以直接运行的离线命令；定制服务单设入口 |
| [SU2](https://github.com/su2code/SU2) | README 顶部使用简洁[项目标识](https://raw.githubusercontent.com/su2code/SU2/master/Docs/logoSU2small.png)，随后介绍定位、版本、CI 和安装方式 | 保持主标题与版本清楚；把真实检查状态链接到证据，不借用其他项目的成熟度或性能承诺 |
| [MOOSE](https://github.com/idaholab/moose) | README 用能力列表介绍框架；[官方 Gallery](https://mooseframework.inl.gov/gallery.html) 为案例配上问题说明、方法和作者来源 | 能力与案例分开；热电案例明确耦合顺序、输入来源和当前复现边界 |
| [FEniCS / DOLFINx](https://github.com/FEniCS/dolfinx) | README 先说明计算环境，再按使用场景、平台及依赖给出安装路线；[官网](https://fenicsproject.org/) 将下载、文档和源码入口集中呈现 | 区分无需 COMSOL 的离线体验与需要本机 COMSOL 6.3 的执行路线，让用户先选适合自己的入口 |

## 本项目的图文约定

- 首屏直接说明：面向 Codex、Claude Code、Cursor，组织可审阅的 COMSOL 工程工作流。
- 当前执行能力写为“已审阅 MPH 的参数化复算和全局结果导出”。几何、物理场、网格与求解器变更通过审阅后的新模型接入。
- 图片中的装配、网格或连线是原创概念示意。配色用于区分组件或阶段，不作为温度、应力、流速等计算结果解释。
- 流程图显示工程假设确认和求解审批两个真实的人类检查点，不暗示无人监督计算。
- 离线测试、Java 编译、实际求解、数值复现和工程验证分别列示。当前验证事实以 [验证记录](validation-status.md) 为准。
- 公开展示不附客户模型、本机运行日志、官方原始 MPH 或其他项目的结果截图。

本项目保留来源链接供读者了解参考对象。未来加入真实计算展示时，应为每幅图附上案例配置、运行记录、数据来源和适用范围。
