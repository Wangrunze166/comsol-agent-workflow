# 最小导热板验证演示

这是为验证执行链而新建的独立模型，不是用户原有研究模型，也不代表完整多物理场耦合已通过验证。`BuildHeatPlate.java` **只构建并保存未求解 MPH**，不执行研究、求解器、数值评估或场图渲染。真实求解仍需针对当前计划确认工程假设并审批。

## 模型与解析基准

| 项目 | 设定 |
| --- | --- |
| 几何 | 2D 矩形，长度 10 mm，高度 5 mm，原点 (0,0) |
| 材料 | 常数各向同性：k=1 W/(m·K)，ρ=1000 kg/m³，Cp=1000 J/(kg·K) |
| 物理场 | 固体稳态导热，无内热源 |
| 边界 | 左侧 293.15 K、右侧 303.15 K；上下沿用默认绝热 |
| 选择 | 用坐标 Box 选择左右边界，要求各选中一个不同实体；不用手写边界编号 |
| 网格 | FreeTri，最大尺寸 L/12，最小尺寸 L/120 |
| 研究／求解／数据集 | std1 / sol1 / dset1；由 COMSOL 6.3 生成默认稳态求解设置 |
| 输出 | case_no=1；Tmean_K=comp1.aveop1(comp1.T)，单位 K |

该边值问题的解析解为 `T(x)=293.15 K + 10 K*x/L`，面积平均温度为 **298.15 K**。本例验收区间是 `[298.149, 298.151] K`。它只能验证此简化问题的数值结果，不能替代网格独立性、守恒或实验验证。

`L_geom=L` 用于几何，`L/12` 用于网格，便于测试直接和间接参数依赖阻断。`T_hot` 仅用于右侧温度边界，是本例允许覆盖的物理标量。

## 已完成的本机真实求解

2026-11-04，用户真实签署工程假设和求解审批，两份 Ed25519 收据验真通过。COMSOL 6.3.0.290 完成了本例加载检查、求解与导出。

![本机COMSOL导出的导热板温度场，左293.15 K、右303.15 K](../../assets/minimal-heat-plate-temperature.png)

*本机 COMSOL 实际导出的 1600 × 1000 温度场 PNG；左侧 293.15 K，右侧 303.15 K。该结果验证本例稳态导热，不代表完整多物理场验证。*

| 实测项 | 结果 |
| --- | --- |
| 平均温度 | 298.1500000000019 K |
| 解析平均温度 | 298.15 K |
| 绝对误差 | 1.9326762412674725 × 10⁻¹² K，低于 0.001 K 阈值 |
| 前置只加载检查 | 32.711377 秒 |
| 运行阶段 | 36.913876 秒 |
| 两阶段合计 | 69.625253 秒，约 69.63 秒 |

上述两阶段各自包含编译与批处理，不含用户审阅／输入等待，也不包含此前一次性构建。原始日志、完成 token、签名收据和求解 MPH 留在私有交付中；公开的[实测指标](verified-results/metrics.csv)、[含单位表格](verified-results/global-results.csv)与温度图来自同一次运行。

网格独立性、守恒与实验验证仍未完成。中断续算当前仅有编译／模拟测试；本次正常结束任务的恢复目录已清理，不构成真实中断恢复验证。

## 构建未求解模型

安装具有所需许可的 COMSOL 6.3，在**空的私有工作目录**中复制构建源文件并执行。以下 PowerShell 命令只构建；COMSOL 安装路径按本机修改。

```powershell
$comsolRoot = 'C:\Program Files\COMSOL\COMSOL63\Multiphysics'
if (Test-Path -LiteralPath '.\heat-plate.mph') { throw 'Choose an empty private directory; the model already exists.' }
& "$comsolRoot\bin\win64\comsolcompile.exe" -classpathadd "$comsolRoot\plugins\*" .\BuildHeatPlate.java
& "$comsolRoot\bin\win64\comsolbatch.exe" -inputfile .\BuildHeatPlate.class -nosave -np 2 -batchlog .\build-batch.log 2>&1 | Tee-Object -FilePath .\build-launcher.log
```

构建器在当前目录保存 `heat-plate.mph`；上面的命令先拒绝已存在的目标。启动日志必须出现边界选择、单域数量和 `BUILD_ONLY_UNSOLVED sol1.isEmpty=true`，并实际存在非空 MPH；COMSOL 启动器可能在 Java 失败时仍返回 0，不能只看退出码。`-nosave` 阻止启动器额外保存；模型保存由构建器显式执行。保留编译和启动日志。

将生成的 MPH 放到私有案例目录，复制 `case.json` 并修改 `model.path`。再依次执行格式检查、计划、只加载 smoke、假设确认、实际求解审批和运行。公开仓库不提交 MPH、许可证、私人路径或审批秘密。默认超时为 300 秒；本机上述运行满足 5 分钟目标，但其他机器或模型仍须实测。

模型预先配置了 `pgT/surf1` 温度场图、`tblMetrics` 表格及 `evalMetrics` 全局评估节点；它们只有在审批后的求解完成后才有数据。

案例的可选 `postprocess` 已声明 `pgT` 导出为 `temperature.png`，并另存含单位的 `global-results.csv`。这两项由执行器在实际求解后生成；纯构建不会产生温度云图或已填充的结果表。加载检查先核验图节点与数据集绑定，输出检查再核验真实文件。完整签名审批与运行步骤见[演示说明](../../docs/demonstration.md)。

## 接口依据与当前证据

- [COMSOL 6.3 物理场与温度边界](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/application_programming_guide.15.25.html)
- [命名选择与 Box](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.56.html)
- [网格 Size](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_mesh.49.099.html)
- [研究和生成默认求解序列](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.60.html)
- [Average 算子](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.26.html)

2026-11-04 在 COMSOL 6.3.0.290 完成 Java 编译和纯构建：左右坐标选择各命中一个不同边界，单域 1 个，网格 192 个单元，最小单元质量 0.7222；保存后 `sol1.isEmpty=true`。本次构建启动到退出用时 34.620 秒，**不是求解耗时**。MPH 和原始日志保存在私有工作目录。

本示例构建、编译、加载和真实求解分别留有记录；求解实测见本页上方结果，项目级证据见[验证状态](../../docs/validation-status.md)。本例数值基准通过不替代网格、守恒、实验或完整多物理场验证。
