![COMSOL Agent Workflow — reviewed models, human approval, reproducible runs](assets/hero.svg)

# COMSOL Agent Workflow

[中文](README.md) · **English** · [Documentation](docs/workflow.md) · [Examples](docs/demonstration.md) · [Issues](https://github.com/Wangrunze166/comsol-agent-workflow/issues/new/choose)

[![Offline checks](https://github.com/Wangrunze166/comsol-agent-workflow/actions/workflows/check.yml/badge.svg)](https://github.com/Wangrunze166/comsol-agent-workflow/actions/workflows/check.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-087e8b.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3273ba.svg)](pyproject.toml)
[![COMSOL 6.3 adapter](https://img.shields.io/badge/COMSOL-6.3%20adapter-526977.svg)](adapters/comsol63/README.md)

**An engineering workflow for Codex, Claude Code and Cursor that turns a reviewed COMSOL model into a traceable simulation plan, an approved run and an evidence report.**

The shared Agent Skill handles engineering context and review. A separate Windows executor targets COMSOL 6.3. The current executable path supports parameterized reruns of reviewed MPH files and real-valued global result exports. Geometry, physics, mesh and solver changes enter through a newly reviewed model.

## What it does

- **Prepare a reviewable case:** record sources, assumptions, units, parameters, model tags and acceptance criteria.
- **Check before computing:** validate supported dimensions, value ranges, input files and expected output coordinates.
- **Require two human decisions:** confirm engineering assumptions, then approve the exact solve plan. Input or executor changes invalidate the plan.
- **Run the reviewed sequence:** generate and compile Java, load a model copy, clear saved solutions, execute the selected solver sequence and save new outputs.
- **Keep the evidence:** preserve input fingerprints, approvals, logs, CSV results, the solved MPH and a report that distinguishes execution from engineering validation.

![Workflow from source model through engineering review and solve approval to results and evidence](assets/workflow.svg)

## Try it without COMSOL

Python 3.10 or newer is required. The offline workflow uses the standard library and runs directly from the repository:

```console
git clone https://github.com/Wangrunze166/comsol-agent-workflow.git
cd comsol-agent-workflow
python -m comsol_workflow --help
python -m unittest discover -s tests -v
python -m comsol_workflow compare examples/offline/actual.csv examples/offline/reference.csv --coordinate time_s --atol 0.01 --rtol 0.001
python -m comsol_workflow plan examples/thermoelectric-pid/case.json --out runs/offline-review
```

The comparison uses **synthetic test data**. The last command creates a review bundle with pending approvals. Because the public example omits the MPH file and local COMSOL installation, the plan reports blocking conditions and stays `not_executed`. Use a new empty output directory for each plan.

The bundle contains `REVIEW.md`, `case.snapshot.json`, generated Java, `plan.json`, two pending approval templates and `report.md`. To install the optional `comsol-workflow` command, run `python -m pip install -e .`.

## Use it with your agent

All three clients share [one authoritative Skill](skills/comsol-multiphysics/SKILL.md). The repository also includes `AGENTS.md`, `CLAUDE.md` and a Cursor rule.

For native project-local Skill discovery, choose **one** of these commands:

```console
python scripts/install_skill.py --client codex --project .
python scripts/install_skill.py --client claude --project .
python scripts/install_skill.py --client cursor --project .
```

The installer copies the Skill into the selected client's project directory and refuses to overwrite an existing copy. Keep the workflow repository as the command working directory. Client discovery paths and API sources are documented in [Interface sources](docs/interface-sources.md).

Example request:

> Follow skills/comsol-multiphysics/SKILL.md for this COMSOL case. Recover the engineering inputs and prepare a reviewable plan. Ask me to confirm the assumptions, then obtain approval before solving. Support every validation claim with evidence.

## Reference case: thermoelectric temperature control

![Conceptual thermoelectric assembly and staged airflow, thermal and PI-control studies](assets/thermoelectric-case.svg)

The example follows [COMSOL Application ID 102421](https://www.comsol.com/model/lumped-thermoelectric-module-with-pid-control-102421): a stationary current sweep and a transient temperature-control study. It preserves several important distinctions:

- Airflow is solved first and then held fixed during the thermal calculation.
- The derivative gain is zero, so this configuration uses **PI control**.
- The stationary case exports 7 current points; the transient case exports 31 times over 60 minutes.
- A module heat-flow metric is not interchangeable with device heating power or cold-side cooling capacity.

The graphics are original conceptual illustrations, **not computed fields or simulation results**. Public examples contain configuration metadata, not the official MPH files. Obtain an authorized model from its source and review its actual tags, selections and settings before execution. See the [demonstration guide](docs/demonstration.md).

## Validation status

| Evidence level | Recorded status |
|---|---|
| Offline tests | 36 tests passed locally on Windows with Python 3.14.6 |
| COMSOL Java compilation | Passed with COMSOL Compile 6.3.0.290; generated code was not executed |
| Three client installer paths | Copy and overwrite-rejection checks passed; native loading in all three clients has not been tested |
| Real solve through this executor | **Not performed** |
| Mesh/time-step independence, conservation and experimental validation | **Not performed** |

See the [validation record](docs/validation-status.md) and [machine-readable evidence](docs/validation-evidence.json). The CI badge links to the current GitHub test result. Earlier calculations in the reference project are separate from validation of this executor.

## Running a real case

Actual execution requires Windows, COMSOL 6.3 and valid licenses for the model's modules. Start with a reviewed MPH, fill the [case configuration](docs/case-format.md), validate it and generate a plan with your installation path. Confirm the engineering assumptions and separately approve that exact solve before invoking `run`.

This MVP does not automatically build arbitrary multiphysics models or prove that a model is physically correct. Its approval receipts are local audit records, not a multi-user authentication system. Field plots, complex-valued exports and new domain-specific builders need further adaptation. The [adapter guide](adapters/comsol63/README.md) documents the execution boundary.

## Documentation

Detailed engineering guides are currently in Chinese:

- [Full workflow](docs/workflow.md) and [case format](docs/case-format.md)
- [Model configuration review template](templates/model-configuration.template.md)
- [Engineering verification plan](templates/verification-plan.template.md)
- [Examples and execution steps](docs/demonstration.md)
- [Interface sources](docs/interface-sources.md) and [presentation references](docs/presentation-references.md)

## Contributing and support

[Open an issue](https://github.com/Wangrunze166/comsol-agent-workflow/issues/new/choose) for a reproducible bug, model-adapter request or scoped improvement. Include the workflow version, COMSOL version, expected behavior and a minimal example you can share. Keep private models, license information and customer data out of public reports.

Read the [contribution guide](CONTRIBUTING.md). For code changes, run `python -m unittest discover -s tests -v` and describe the evidence behind any claimed COMSOL behavior. Keep offline tests, compilation and real solver validation distinct.

Custom work can include model onboarding, domain-specific builders, solver diagnosis, team deployment and reproducible engineering reports. See [service scope and delivery criteria](docs/commercialization.md), or open a [scoped request](https://github.com/Wangrunze166/comsol-agent-workflow/issues/new/choose).

## License

Original project code, documentation and illustrations are available under [MIT](LICENSE). COMSOL software, trademarks, official models and third-party materials retain their respective terms. This is an independent project and is not affiliated with or endorsed by COMSOL.
