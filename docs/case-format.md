# 案例文件与交付格式

v0.2 继续使用 UTF-8 JSON 和 `schema_version=1`；相对输入路径以案例文件为基准。模板由 `python -m comsol_workflow init private/my-case` 生成。参考[最小导热板](../examples/minimal-heat-plate/case.json)和[热电案例](../examples/thermoelectric-pid/case.json)。`validate` 不会打开 MPH；`smoke` 才启动 COMSOL 做只加载检查。

| 字段 | 含义 |
| --- | --- |
| provenance | 来源和性质；synthetic_fixture 禁止进入真实执行器 |
| model | MPH、6.3 版本、study/solver/dataset、全部 solution/store 清理标签和依赖 |
| parameters | 明确覆盖的参数；空数组表示保留原参数 |
| constraints | less_than 约束，先换算 SI 并核对同量纲 |
| engineering | 几何、材料、物理、耦合、边界、网格、求解器、假设及验收标准 |
| execution | 核心数、超时及可选恢复保存间隔 |
| exports | 实数全局指标名称、COMSOL 表达式、单位和量类型 |
| postprocess | 可选场图 PNG 与结果表格 CSV |
| results | 坐标、预期完整扫描／时间点、误差阈值、参考 CSV、结果界限 |
| validation | not_run/planned/passed/failed/not_applicable；passed 须有有效证据文件 |

## 参数与实际引用

```json
{
  "name": "R", "value": 2, "unit": "ohm", "quantity": "resistance",
  "scope": "physics_scalar", "source": "审阅后的器件参数表", "min": 0.1, "max": 10
}
```

参数必须已存在于模型。min/max 使用该条目的单位；无量纲量使用 `1`。量纲集合见 `comsol_workflow/units.py`，未支持单位直接拒绝，不自动猜测。复合单位支持乘除、括号和整数幂，如 `A/(K*s)`；绝对温度可用 `degC`，温差使用 `K`。复杂模型表达式保留在 MPH 中，不交给 Python `eval`。

`scope` 声明不能证明安全。原生只加载驱动读取几何／网格／选择属性及参数表达式，检查直接和间接依赖；命中则阻断覆盖。API 属性未知、读取失败或不支持的表达式间接引用，会阻断无法安全判断的参数覆盖；不会默认放行。

`engineering.reference_parameters` 仅为审阅摘要，不会写入模型。具体边界、材料选择和求解组仍从实际模型确认。单物理场示例可在 couplings 中明确记录 not_applicable 及原因，不虚构耦合。

## 执行与恢复间隔

```json
"execution": {
  "cores": 2,
  "timeout_seconds": 300,
  "recovery_interval_seconds": 30
}
```

cores 是 1..256 的整数，timeout_seconds 是 1..604800 的整数；编译另有不超过 300 秒的上限。可选 recovery_interval_seconds 必须为 **1..3600 的整数**，省略时沿用 COMSOL 偏好。它会设置求解器 Advanced 的 manual 保存间隔和 oneveryiteration 保存频率，依据[官方属性表](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_solver.51.17.html)。实际恢复依赖求解器已写出的有效状态，间隔字段不保证恢复文件一定存在。

恢复由 `resume` 命令创建新计划和恢复快照，使用 `loadRecovery` / `continueRun`，需要新的 assumptions/resume 签名。无法恢复时停止，不静默从头重跑。

## 可选后处理

```json
"postprocess": {
  "field_plot": {"tag": "pgT", "filename": "temperature.png"},
  "table": {"filename": "global-results.csv"}
}
```

field_plot.tag 必须是已存在、直接绑定声明数据集的场图节点；本字段不自动搭建任意模型的场图。文件名是单个本地文件名，须以字母开头，仅含字母、数字、下划线或连字符；分别使用 .png/.csv 后缀。不能使用目录路径或保留名称 metrics.csv。

表格包含 exports 中的全局指标及单位，数据来自本次解。驱动通过带运行 token 的 stdout 载荷传递指标／表格，由宿主核验并写入限定路径；PNG 和 MPH 使用 COMSOL 原生接口，不降低 Java 文件安全策略。

比较采用 `abs(actual-reference) <= atol + rtol*abs(reference)`；atol 按每列声明单位解释。混合量纲且精度要求不同时应分别设置可审核阈值，不能盲用统一值。比较不排序、不插值，也不把仅含坐标的 CSV 视为物理验证。

## 签名、证据与复现

计划绑定案例、输入／依赖、证据文件、生成 Java、Python 执行器、启动器及受信公钥。改动后重新计划。待审批模板不是收据；实际运行要求 Ed25519 验签成功的两份原始收据，手填 approved=true 无效。求解／恢复签名还绑定此前的假设收据。

用户可在自己控制的受信终端使用 [human-review.ps1](../scripts/human-review.ps1) 引导一次新求解；TTY 不构成身份保证，私钥与口令必须位于 Agent 权限之外。见[安全边界](approval-security.md)和[演示步骤](demonstration.md)。

运行目录保留计划、输入摘要、签名收据、命令／耗时、启动器和批处理日志、指标、可选图片／表格及新 MPH。Java stdout 的 token 与产物检查用于关联当前运行；退出码 0 不足以判成功。原始记录不覆盖，迁移后修正输入路径并重新计划。模型、许可证、私人路径和签名秘密不进入公开仓库；环境差异在报告中单列。实现、编译、加载和真实求解分别记录，当前状态见[验证记录](validation-status.md)。
