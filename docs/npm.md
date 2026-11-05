# npm 安装与使用

`comsol-agent-workflow` 的 npm 发行提供 Node.js 命令入口，并运行随包携带的 Python 执行器。需要 **Node.js 22+、npm 和 Python 3.10+**。npm 包版本 **0.2.1** 增加分发入口，随包 Python 执行器保持 **0.2.0**，其代码及已有实测证据指纹未因打包而改变。

## 安装和案例初始化

临时调用固定版本（Run a pinned version）：

```console
npx comsol-agent-workflow@0.2.1 --help
npx comsol-agent-workflow@0.2.1 init ./my-case
```

固定安装（Install the CLI）：

```console
npm install --global comsol-agent-workflow@0.2.1
comsol-workflow --version
comsol-workflow --help
```

`init` 写入待补充的 `case.json`；已有同名文件会报错，不覆盖。填写真实模型来源、参数和工程要求后，再使用 `validate` 与 `plan`。安装和初始化不求解、不产生批准收据。

包内包括 Python 源码、Skill、模板、文档、公开示例和原创图片；不附 Python 运行时、COMSOL 软件、许可、MPH 模型或私钥。没有自动安装 Python 依赖或启动 COMSOL 的安装钩子。

## Python 与签名依赖

入口自动查找本机 Python 3.10+。需要使用指定虚拟环境时，将 `COMSOL_WORKFLOW_PYTHON` 设置为该环境的 **Python 可执行文件路径**；值不能包含参数或整段 shell 命令。显式指定的解释器不可用时会报错，不改用其他环境。

Windows PowerShell 示例（Select a signing environment）：

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install "cryptography>=46"
$env:COMSOL_WORKFLOW_PYTHON = (Resolve-Path ".venv\Scripts\python.exe").Path
comsol-workflow --help
```

macOS / Linux 的离线命令环境：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'cryptography>=46'
export COMSOL_WORKFLOW_PYTHON="$PWD/.venv/bin/python"
comsol-workflow --help
```

`cryptography` 用于签名和验签；纯离线比较不需要它。入口以 Python 隔离模式运行，忽略 `PYTHONPATH` 和用户级 site-packages，避免从调用目录加载同名模块。因此请将依赖安装到所选解释器的虚拟环境内。实际 COMSOL 执行仍以 Windows / COMSOL 6.3 为支持范围。

## Skill 与随包资源

将共享 Skill 安装到当前项目（Install a project-local Skill）：

```console
comsol-workflow install-skill --client codex --project .
comsol-workflow --package-root
```

将 `codex` 换成 `claude` 或 `cursor` 可安装到相应项目发现目录。已有同名 Skill 不会被覆盖。`--package-root` 输出安装包根目录，可据此打开 `docs/`、`templates/`、`examples/` 和适配器说明。不要把案例、私钥或运行产物写入 npm 安装目录。

文档中 `python -m comsol_workflow ...` 的执行器命令可替换为 `comsol-workflow ...`；命令保持当前工作目录，案例和输出路径仍按原 CLI 规则解析。下例从已安装资源读取合成数据，进行离线比较：

```powershell
$workflowRoot = comsol-workflow --package-root
comsol-workflow compare "$workflowRoot/examples/offline/actual.csv" "$workflowRoot/examples/offline/reference.csv" --coordinate time_s --atol 0.01 --rtol 0.001
```

建议固定包版本，并在工程交付中记录 `comsol-workflow --version`、Python 版本和执行计划指纹。更换执行器或输入后按原流程重新生成计划及签名。

## 审批与验证边界

`plan`、`smoke`、`approve`、`run` 等命令仍由原执行器处理。启动器保留终端交互和退出状态，不代签工程假设或求解审批。密钥与信任边界见[审批安全说明](approval-security.md)。

v0.2 最小导热板的真实 COMSOL 运行证据见[验证状态](validation-status.md)。npm 安装检查证明包可以安装和调用，不增加新的仿真验证结论。真实中断续算、原热电多物理场案例和完整工程验证仍需单独完成。

`scripts/human-review.ps1` 面向源码目录，直接调用 Python 模块；npm 用户按完整演示逐条执行 `comsol-workflow plan`、`smoke`、`approve` 和 `run`。该辅助脚本不会自动识别 npm 启动器。
