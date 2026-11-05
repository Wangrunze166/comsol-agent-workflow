#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);

if (args.length === 1 && args[0] === '--version') {
  console.log(JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8')).version);
  process.exit(0);
}
if (args.length === 1 && args[0] === '--package-root') {
  console.log(root);
  process.exit(0);
}

// Use argv arrays, never a shell. An explicit interpreter is authoritative.
const requestedPython = process.env.COMSOL_WORKFLOW_PYTHON;
const candidates = requestedPython
  ? [[requestedPython]]
  : process.platform === 'win32'
    ? [['python'], ['py', '-3'], ['python3']]
    : [['python3'], ['python']];
const flags = ['-I', '-B', '-X', 'utf8'];
const check = 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)';
const python = candidates.find(([exe, ...prefix]) => {
  const probe = spawnSync(exe, [...prefix, ...flags, '-c', check], {
    stdio: 'ignore', timeout: 10000, windowsHide: true,
  });
  return !probe.error && probe.status === 0;
});
if (!python) {
  console.error('Python 3.10+ is required. Install Python or set COMSOL_WORKFLOW_PYTHON to its executable path (without command arguments).');
  process.exit(1);
}

const installSkill = args[0] === 'install-skill';
if (args.length === 1 && ['--help', '-h'].includes(args[0])) {
  console.log('npm launcher: --version | --package-root | install-skill --client codex|claude|cursor --project PATH');
  console.log('All workflow commands below use the bundled Python executor.\n');
}
// Isolated Python excludes cwd, PYTHONPATH and user site-packages. Insert only
// this installed package, so a caller's same-named module cannot replace it.
const bootstrap = installSkill
  ? 'import runpy, sys; script = sys.argv.pop(1); sys.argv[0] = script; runpy.run_path(script, run_name="__main__")'
  : 'import sys; sys.path.insert(0, sys.argv.pop(1)); sys.argv[0] = "comsol-workflow"; from comsol_workflow.cli import main; raise SystemExit(main())';
const [exe, ...prefix] = python;
const result = spawnSync(exe, [
  ...prefix, ...flags, '-c', bootstrap,
  installSkill ? resolve(root, 'scripts/install_skill.py') : root,
  ...(installSkill ? args.slice(1) : args),
], { stdio: 'inherit' });
if (result.error) {
  console.error(`Could not start Python: ${result.error.message}`);
  process.exit(1);
}
if (result.signal) {
  // Match conventional interrupted-command exit codes without retrying a solve.
  process.exit(result.signal === 'SIGINT' ? 130 : result.signal === 'SIGTERM' ? 143 : 1);
}
process.exit(result.status ?? 1);
