# 10K+ 星工程参考与本轮改进依据

本轮仅选用 GitHub 星数不少于 **10,000** 的工程／科学计算项目。下表通过 GitHub REST API 的 `stargazers_count` 于 **2026-11-04** 实时核验；星数是当日快照，后续会变化。源码链接固定到核验时的提交，避免主分支更新后无法复查。

这些项目提供设计参考，不是本项目的依赖，也不代表它们支持 COMSOL 或提供人类审批机制。本项目是否真正通过 COMSOL 6.3 求解，见[验证状态](validation-status.md)。

| 项目 | 当日 stars | 核验入口 | 本轮借鉴内容 |
| --- | ---: | --- | --- |
| [FreeCAD](https://github.com/FreeCAD/FreeCAD) | 35,115 | [GitHub API](https://api.github.com/repos/FreeCAD/FreeCAD) | 求解阶段分离、表达式依赖图、CAD／CAE 项目介绍方式 |
| [Taichi](https://github.com/taichi-dev/taichi) | 28,454 | [GitHub API](https://api.github.com/repos/taichi-dev/taichi) | 参数集中声明、短小的可运行仿真示例、结果演示 |
| [MuJoCo](https://github.com/google-deepmind/mujoco) | 16,056 | [GitHub API](https://api.github.com/repos/google-deepmind/mujoco) | 模型加载与仿真分离、完整状态保存与恢复 |
| [Open3D](https://github.com/isl-org/Open3D) | 14,173 | [GitHub API](https://api.github.com/repos/isl-org/Open3D) | 实际场景的离屏图片导出、清晰的结果展示 |

## 对应本轮交付要求

### P0：小模型完整运行及证据

Taichi 的 [`mpm128.py`](https://github.com/taichi-dev/taichi/blob/ba0e81dce559fb63a5958bf82feb1d00c55c02fe/python/taichi/examples/simulation/mpm128.py) 集中声明网格、时间步和物理参数，并将状态初始化、数值更新、显示分开。借鉴这种可读的小示例结构，为 COMSOL 准备明确标为演示的最小模型，记录输入、运行时间、输出和验收条件。

“5 分钟内”必须来自本机实测；参考项目的星数、动画和示例规模均不能证明 COMSOL 运行时间。本项目验收应保留 `batch.log`、`launcher.log`、审批收据、`metrics.csv`、输出模型及其文件摘要。公开证据应去除私人路径、用户名、许可证信息和签名秘密；审批收据不得包含私钥或 HMAC 密钥。

### P1：加载检查与实际求解分开

FreeCAD 的 [`femsolver/run.py`](https://github.com/FreeCAD/FreeCAD/blob/0cafef1e58284d08a244f9eba85aee0002e3e350/src/Mod/Fem/femsolver/run.py) 明确定义检查、准备、求解、结果阶段。MuJoCo 的 [`sample/basic.cc`](https://github.com/google-deepmind/mujoco/blob/24b240a8b53741e0e2b875441b3b92bc12b27661/sample/basic.cc) 先加载模型、处理错误，再进入 `mj_step` 循环。

对应到 COMSOL：提供只加载 MPH、检查组件／物理场／网格／研究／结果标签的 smoke 模式；成功加载不等于收敛，更不等于物理验证通过。检查模式不得调用求解器，也不得把清空解或重建网格隐藏在“加载”步骤中。

### P1：从实际表达式反查几何和网格依赖

FreeCAD 的 [`PropertyExpressionEngine.cpp`](https://github.com/FreeCAD/FreeCAD/blob/0cafef1e58284d08a244f9eba85aee0002e3e350/src/App/PropertyExpressionEngine.cpp) 通过表达式依赖建立图，并检测循环。借鉴的是读取真实依赖、追踪间接引用的原则，不是复用 FreeCAD 的 API。

COMSOL 执行器应通过 Java API 检查实际几何／网格节点属性及参数表达式链。参数声明 `scope` 只能作为意图，不能替代检查；参数直接或间接影响几何／网格时应阻断只修改物理参数的运行路径，并报告命中节点和属性。不能完整检查的属性应明确报错或要求人工处理，不能默认为安全。

### P2：恢复保存的求解状态

MuJoCo 的[状态与控制说明](https://mujoco.readthedocs.io/en/stable/programming/simulation.html#state-and-control) 区分状态子集与完整积分输入，并提供获取／恢复状态的接口。这说明“恢复”需要足够的求解状态，不能仅用相同输入重跑冒充续算。

COMSOL 必须使用其原生 recovery 机制；MuJoCo 的接口不能直接移植。恢复前应核验恢复目录、模型／配置身份和实际恢复文件，保存本次启动记录。仅创建 `recoverydir` 或生成命令不能算恢复实测通过。

### P2：导出实际图片与表格

Open3D 的 [`render_to_image.py`](https://github.com/isl-org/Open3D/blob/b6c5e196384ad71e75b6e6f9c5da22d046221f1d/examples/python/visualization/render_to_image.py) 显式配置画面尺寸、场景、相机并写出图片。对应到 COMSOL：绑定真实数据集和结果节点，导出最小场图与含单位的数值表格，验证文件存在且内容可读。场图能打开只证明图像交付成功，数值正确性仍需单独核验。

## P0：审批不可代签的实际安全边界

这部分依据安全接口的一手文档，**不宣称上述高星工程项目已经实现同类审批**。

- 独立 `approve` 命令加交互式 TTY 能减少误触，但不能单独证明人类授权。Python [`os.isatty`](https://docs.python.org/3/library/os.html#os.isatty) 只判断描述符是否连接终端；Agent 可使用伪终端，因而仍可能满足条件。
- [HMAC](https://www.rfc-editor.org/rfc/rfc2104) 的生成和验证使用共享秘密。若 Agent 能读取该秘密、调用不受保护的签名接口或修改验证器，就不能声称不可代签。用户侧 HMAC 只有在密钥和签名动作都位于 Agent 无权访问的边界之外时才有意义。
- 可选实现是人类持有签名私钥，执行器仅保存固定受信公钥；签名绑定模型／配置摘要、动作、时效和一次性请求标识。私钥和解锁口令不得保存在 Agent 可读目录或环境变量内。硬件密钥可强化边界；[OpenSSH 8.2 发布说明](https://www.openssh.org/txt/release-8.2) 描述了默认需要用户触碰的安全密钥，关闭触碰会削弱该机制。
- 宿主授权通道也可以形成边界，但必须核实宿主是否实际提供不可由 Agent 自发生成的确认事件，以及执行器是否验证该事件。仓库中的说明、布尔字段或身份字符串本身不构成宿主授权。

**可承诺的范围：受信且未被修改的执行器拒绝缺失、过期、篡改或绑定对象不匹配的审批收据。** 若 Agent 与用户拥有同等系统权限、能修改执行器／受信公钥，或能直接运行 COMSOL，则单个仓库脚本无法保证整台机器上的求解不可绕过；更强保证需要独立用户权限、受保护的签名服务或宿主级执行限制。

## GitHub 介绍与图片使用

参考上述项目 README 的信息组织：一句话说明用途、真实结果图、最短可运行示例、能力与验证边界、安装／使用入口、贡献与许可证。介绍中应说明本项目是面向 Codex／Claude Code／Cursor 的 COMSOL 工程工作流，不应把参考项目的数值算法或性能写成本项目能力。

图片应使用本项目自己的架构示意和实际演示导出，并明确区分示意图与求解结果。本轮未复制第三方图片或源码；若将来复制，应逐项检查对应文件的许可与署名要求。[展示参考](presentation-references.md)与上表采用同一组“10K+ 星”项目。
