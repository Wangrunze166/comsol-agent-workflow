# 演示说明

v0.2 将离线流程、模型构建、只加载检查、实际求解与中断恢复分开演示。**最小导热板已通过用户两份 Ed25519 签名验真，完成本机真实求解及 PNG／表格导出；前置加载检查与运行合计 69.625253 秒，不含人工输入等待。** 该结果验证单场示例的执行链；真实中断恢复和完整工程验证仍未完成。最新状态见[验证记录](validation-status.md)。

## A：无需 COMSOL 的离线体验

`examples/offline` 包含明确标注的合成数据，用于观察比较、日志诊断和拒绝行为。它不是 COMSOL 结果，也不是热电案例的实测数据。

```console
python -m comsol_workflow --help
python -m comsol_workflow compare examples/offline/actual.csv examples/offline/reference.csv --coordinate time_s --atol 0.01 --rtol 0.001
python -m comsol_workflow diagnose examples/offline/solver-synthetic.txt
python -m comsol_workflow plan examples/minimal-heat-plate/case.json --out runs/offline-review
```

最后一条生成 `REVIEW.md`、案例快照、两份 Java 驱动、计划、待审批请求和报告。公开案例没有附 MPH 或本机安装路径，缺失条件会明确列出，状态保持 `not_executed`。不要伪造模型或审批记录绕过拒绝；重复演示使用新的空目录。

开发检查可安装可选审批依赖后运行：

```console
python -m pip install -e ".[approval]"
python -m unittest discover -s tests -v
```

离线测试不检查 COMSOL 许可，不证明模型加载或求解收敛。

## B：最小导热板，先构建再审批

[最小模型](../examples/minimal-heat-plate/README.md)是本次新增的执行链验证案例，不是原有多物理场研究模型。

| 项目 | 设定与验收 |
| --- | --- |
| 几何 | 10 × 5 mm 二维矩形；左右边界按坐标选择，各必须选中一个不同实体 |
| 材料 | k=1 W/(m·K)，ρ=1000 kg/m³，Cp=1000 J/(kg·K)，常数各向同性 |
| 物理条件 | 稳态导热，无内热源；左 293.15 K，右 303.15 K，上下绝热 |
| 网格 | FreeTri，最大尺寸 L/12，最小尺寸 L/120 |
| 基准 | 解析平均温度 298.15 K；接受区间 [298.149, 298.151] K |
| 输出 | case_no=1、Tmean_K；可选 temperature.png 与 global-results.csv |
| 时间 | 2 核、300 秒超时；本机前置 smoke 32.711377 秒，运行阶段 36.913876 秒，合计 69.625253 秒，不含人工输入 |

按示例 README 编译并运行 `BuildHeatPlate.java`。它只构建几何、材料、网格和输出节点，保存未求解 MPH；不会调用求解器。2026-11-04 本机构建用时 34.620 秒，网格 192 单元、最小质量 0.7222，保存后 `sol1.isEmpty=true`。这些数字不属于求解证据。

随后用户在受信终端完成工程假设和求解签名。真实计算的平均温度为 **298.1500000000019 K**，解析值 298.15 K，绝对误差 **1.9326762412674725 × 10⁻¹² K**，通过 0.001 K 阈值。已保存本次原始日志、完成 token、两份签名收据、指标 CSV、含单位表格、1600 × 1000 PNG 和新 MPH。

![本机COMSOL导出的导热板温度场](../assets/minimal-heat-plate-temperature.png)

*实际温度场：左侧 293.15 K、右侧 303.15 K；由本机 COMSOL 6.3.0.290 导出。该单场演示不代表多物理场模型通过验证。*

公开数据：[metrics.csv](../examples/minimal-heat-plate/verified-results/metrics.csv) · [含单位表格](../examples/minimal-heat-plate/verified-results/global-results.csv)。耗时包括各阶段编译和批处理，不包括用户审阅／输入等待，也不包含此前一次性构建。网格独立性、守恒和实验验证尚未完成。

将 MPH 和案例配置放在私有目录，修正 `model.path`。下述示意路径需按本机修改：

```powershell
python -m comsol_workflow validate private/heat-plate/case.json
python -m comsol_workflow doctor --root 'C:\Program Files\COMSOL\COMSOL63\Multiphysics'
```

`doctor` 只检查启动器路径，不检验许可或数值行为。

### 用户准备签名密钥

本步骤由用户在受信终端执行，私钥和口令位于 Agent 无权访问的边界外。下面的 `X:\operator-only` 代表用户自行管理的受保护位置，不是自动创建安全边界的功能。

```powershell
python -m comsol_workflow approval-keygen --private-key 'X:\operator-only\approval-private.pem' --public-key 'X:\operator-only\approval-public.pem'
```

用户将公钥提供给计算端，核验指纹，并保护计算端的公钥与执行器。私钥口令仅在用户终端隐藏输入，不放进参数、环境变量、聊天或仓库。TTY 只拒绝管道误用，不能防止 Agent 创建伪终端；完整约束见[审批安全说明](approval-security.md)。不要让 Agent 创建其已知口令的“用户密钥”并代签。

### 生成计划并进行只加载检查

计算端仅持有用户提供的公钥：

```powershell
python -m comsol_workflow plan private/heat-plate/case.json --out runs/heat-plate-001 --comsol-root 'C:\Program Files\COMSOL\COMSOL63\Multiphysics' --public-key trust/approval-public.pem
python -m comsol_workflow smoke runs/heat-plate-001
```

`dry-run` 是 `smoke` 的别名。两者会启动 COMSOL，加载模型副本并检查研究／求解／数据集标签、可选场图绑定和参数依赖；不调用研究或求解器、不重建几何或网格、不清空已有解、不保存新 MPH。它与只读 JSON 的 `validate` 不同，也不等同于原生批处理的所有测试选项。

检查器从 Java API 返回的几何／网格属性反查参数表达式链。示例中 `L_geom=L` 影响几何，`L/12` 影响网格；把 `L` 错标成 `physics_scalar` 应被阻断，并报告命中路径。`T_hot` 只影响温度边界。引用检查的范围与未能读取的项必须保留在检查报告中，不能用人工填写的 scope 替代模型检查。

### 用户签署两个决定

用户审阅 `REVIEW.md`、案例、模型、生成驱动和加载检查结果后，先确认工程假设，再单独批准当前求解。以下命令由用户在受信环境运行；示例路径仅供说明。

```powershell
python -m comsol_workflow approve runs/heat-plate-001 --stage assumptions --private-key 'X:\operator-only\approval-private.pem' --public-key trust/approval-public.pem --out approvals/heat-plate-assumptions.json
python -m comsol_workflow approve runs/heat-plate-001 --stage solve --private-key 'X:\operator-only\approval-private.pem' --public-key trust/approval-public.pem --assumptions approvals/heat-plate-assumptions.json --out approvals/heat-plate-solve.json
```

创建密钥时两次输入口令只是创建并确认密钥口令，**不等于完成审批签署**。每次 `approve` 还需依次填写姓名／操作者标识、`Decision note`（审阅说明），输入终端当前显示的完整 `APPROVE` 短语，再输入创建密钥时的原口令。工程假设与求解两个阶段各签一次。口令输入没有回显是正常行为，不要把口令发到聊天中。

执行器核验 Ed25519 签名、计划指纹、阶段、时间顺序及上游假设收据。手填 `approved:true` 或修改签名 JSON 不再有效。输入或执行代码变化后必须重新计划与签名。

### 在签名验证通过后执行

```console
python -m comsol_workflow run runs/heat-plate-001 --assumptions approvals/heat-plate-assumptions.json --approval approvals/heat-plate-solve.json
python -m comsol_workflow report runs/heat-plate-001
```

每个计划只尝试一次。验收应同时检查当前完成标记、`launcher.log`、`batch.log`、`metrics.csv`、输出 MPH、坐标和温度界限。COMSOL 曾在 Java 执行失败时返回退出码 0，因此不能仅用退出码判成功。实际计算用时来自本次执行记录，不采用构建耗时或预设动画。

本次实测中，运行 token 位于 `launcher.log` 和完成标记；`batch.log` 只有批处理头部，求解进度正文在 `progress.log`。三类日志应同时保留，不能假定每个日志都含 token。另对运行记录中的 15 个结果文件摘要进行了独立核验，全部匹配。

### 可选场图和表格

案例可声明：

```json
"postprocess": {
  "field_plot": {"tag": "pgT", "filename": "temperature.png"},
  "table": {"filename": "global-results.csv"}
}
```

场图须预先配置并绑定已审阅的数据集；PNG 来自本次求解结果，表格包含全局指标及单位。缺失节点、空文件或错误格式应使交付检查失败。导出图像不证明数值正确，工程验证仍单独记录。

## C：中断后从恢复数据续算

执行器启用原生 recovery 保存。仅当失败或中断的运行确实留下有效模型恢复目录时，才创建新恢复计划；原计划与原始日志继续保留。

```console
python -m comsol_workflow resume runs/interrupted-001 --out runs/resume-001 --public-key trust/approval-public.pem
python -m comsol_workflow smoke runs/resume-001
```

若原运行没有记录恢复模型路径，审查它的 recovery 目录后用 `--recovery-model` 指定实际子目录。目录必须位于原运行的 recovery 根内；仅存在空目录不能证明可恢复。

用户针对新计划重新签署 `assumptions`，然后签署 `--stage resume` 并绑定新假设收据；再用 `run` 提交这两份收据。恢复驱动调用 `loadRecovery` 和 `continueRun`，不静默退回初始模型重算。**当前仅有恢复接口编译和模拟测试，真实中断续算尚未验证。** 本次导热板正常结束后 recovery 目录已清理，不能作为中断恢复成功的证据；见验证记录。

## D：热电模块与 PI 控制参考

保留 [COMSOL 官方案例 102421](https://www.comsol.com/model/lumped-thermoelectric-module-with-pid-control-102421) 及其[官方说明](https://www.comsol.com/model/download/1479601/lumped_thermoelectric_module_PID_control.pdf)对应的复现配置。公开仓库仅提供元数据，模型由使用者按许可获取；实际设置以审阅后的 MPH 为准。

| 项目 | 参考配置 |
| --- | --- |
| 几何 | 空气域 200 × 400 × 120 mm；底座 100 × 100 × 4 mm；8 片高 38 mm、热学厚 2.5 mm 的壳翅片 |
| 器件／模块 | 器件 15 × 15 × 5 mm；TEM 40 × 40 × 4.5 mm；接触层 2.5 mm |
| 环境 | 20°C，入口 0.5 m/s |
| 热源 | 稳态 4 W；瞬态在 10 min 后开启，平滑宽度 2 s |
| 热电参数 | 最大电流 4 A、最大热流率 40 W、最大温差 70 K、电阻 2 Ω |
| 研究 | 电流 0.5–3.5 A，间隔 0.5 A；瞬态 0–60 min，每 2 min 输出 |
| 控制 | 设定值 6.5°C；kP=−0.05 A/K，kI=−0.005 A/(K·s)，kD=0；电流限幅 0.01–4 A |
| 耦合顺序 | 先稳态流场，后冻结流场求热学；瞬态包含控制积分变量 |

名称沿用 PID，但该配置实际为 PI，且不是全瞬态双向流热耦合。保留原控制器偏置与限幅表达式。器件平均温度、TEM 热流率与温差的表达式及数据集必须从实际模型核验；模块热流率不能直接等同器件功率或冷端制冷量。

先完成稳态案例，再按独立计划安排瞬态。目标输出时间点不等于内部积分步长。历史本机复现报告不自动计入新执行器验证；网格、时间步、守恒和实验检查保持各自实际状态。

## 演示画面与公开证据

介绍方式参考经核验的 [FreeCAD、Taichi、MuJoCo、Open3D](presentation-references.md)，四者在 2026-11-04 均超过 10K stars。现有 SVG 是原创概念图；没有真实求解证据时，画面注明“离线流程”或“构建／加载检查”，不显示虚构云图、结果曲线或求解成功动画。

公开展示建议依次呈现模型来源、案例、只加载检查、用户签名、实际执行记录、数值检查和报告。任何尚未执行的阶段明确标为未验证。
