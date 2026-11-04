# 案例文件与交付格式

模板由 `python -m comsol_workflow init private/my-case` 生成；真实案例可参照 `examples/thermoelectric-pid/`。JSON 使用 UTF-8，`schema_version=1`，相对路径均相对于案例文件。`validate` 是运行时格式与物理量检查入口，不会打开 MPH。

| 字段 | 含义 |
|---|---|
| provenance | 原始来源与性质；synthetic_fixture禁止启动真实执行器 |
| model | 原MPH、6.3版本、study/solver/dataset标签、所有solution/store清理标签和依赖文件 |
| parameters | 本次明确覆盖的参数；空数组表示保留模型原参数 |
| constraints | 已列参数的less_than约束，先换算SI、核对同量纲再比较 |
| engineering | 几何、材料、physics、耦合、初边值、网格与求解器审阅、假设和验收标准 |
| execution | 核心数与单次求解超时；编译另有不超过300 s的上限 |
| exports | 实数全局指标的名称、COMSOL表达式、单位、物理量类型 |
| results | 坐标、完整预期时间/扫描点、坐标误差、逐点比较阈值及可选输出界限 |
| validation | 各工程检查为not_run/planned/passed/failed/not_applicable，passed需有效证据文件 |

参数覆盖示例（仅演示格式，不代表批准修改）：

```json
{
  "name": "R", "value": 2, "unit": "ohm", "quantity": "resistance",
  "scope": "physics_scalar", "source": "已审阅的器件参数表及作用范围", "min": 0.1, "max": 10
}
```

参数必须已存在于模型全局参数表。min/max以该条目的单位表示；无单位量使用`1`。支持的量纲与单位集合在 `comsol_workflow/units.py`，未支持的单位不会自动猜测或转换。复合单位使用 `*`、`/`、括号和整数幂，例如`A/(K*s)`；`degC`仅用于绝对温度，温差使用`K`。原模型复杂函数、控制表达式保留在审阅后的 MPH 中，不交给 Python `eval`。

`engineering.reference_parameters` 是示例中的人类审阅摘要；执行器不会写入这些参数，也不能把摘要检查当成 MPH 内部核验。任意边界号、material/physics选择和求解组仍要从具体模型确认。

默认比较规则对每列使用 `abs(actual-reference) <= atol + rtol*abs(reference)`；`atol` 的数值按各列已声明单位解释。混合量纲且精度要求不同的指标，应分别导出同坐标CSV并用各自批准阈值比较，或实现并验证逐指标容差扩展，不能盲用统一阈值。比较不排序、不插值，也不把仅含坐标的CSV视为物理验证。

## 审批与复现

计划指纹绑定案例、输入文件、声明依赖、报告证据、生成Java、Python执行器和启动程序。修改任何绑定内容后重新计划。确认文件记录本地人类决定；拥有工作区写权限的人仍能改写记录，因此它不是身份认证或恶意代码隔离机制。

运行目录保存原始计划、输入哈希、两份审批记录、执行命令/返回码/耗时、日志、CSV和新MPH。复现时保留原始记录不覆盖，迁移输入与依赖后更新路径，生成新计划并审批。模型二进制及材料/CAD通常属于私有交付，公开仓库只含工具和示例元数据。工具链插件、操作系统与硬件并未逐文件冻结，环境差异需在复现报告记录。
