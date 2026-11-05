import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const source = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const metadata = JSON.parse(readFileSync(join(source, 'package.json'), 'utf8'));

function run(executable, args, options = {}) {
  const result = spawnSync(executable, args, {
    encoding: 'utf8', timeout: 90000, windowsHide: true, ...options,
  });
  assert.ifError(result.error);
  assert.equal(result.signal, null, `Process was interrupted: ${result.signal}`);
  return result;
}

function succeeded(result) {
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  return result.stdout;
}

function sameFile(actual, expected) {
  // Windows' short and long path spellings can differ between Node and Python.
  // Compare the underlying filesystem object, not a spelling of its pathname.
  const actualStat = statSync(actual, { bigint: true });
  const expectedStat = statSync(expected, { bigint: true });
  assert.deepEqual(
    [actualStat.dev, actualStat.ino], [expectedStat.dev, expectedStat.ino],
    `Expected the same filesystem object: ${actual} and ${expected}`,
  );
}

test('the packed npm artifact works from an isolated installed location', { timeout: 240000 }, async (t) => {
  const npmCli = process.env.npm_execpath;
  assert.ok(npmCli && existsSync(npmCli), 'Run this suite with npm test so the active npm CLI is known.');
  const scratch = realpathSync(mkdtempSync(join(tmpdir(), 'comsol-npm-test-')));
  try {
    const npm = (args, cwd = source) => run(process.execPath, [npmCli, ...args], { cwd });
    const pack = JSON.parse(succeeded(npm([
      'pack', '--json', '--ignore-scripts', '--pack-destination', scratch,
    ])))[0];
    const install = join(scratch, 'isolated install');
    mkdirSync(install);
    succeeded(npm([
      'install', '--prefix', install, '--ignore-scripts', '--no-audit', '--no-fund',
      '--offline', join(scratch, pack.filename),
    ], install));
    const installed = join(install, 'node_modules', metadata.name);
    const entry = join(installed, 'bin', 'comsol-workflow.mjs');
    const caller = join(scratch, '用户 模型 workspace');
    mkdirSync(caller);
    const cli = (args, options = {}) => run(process.execPath, [entry, ...args], { cwd: caller, ...options });

    await t.test('tarball has the required public resources and exact Python executor bytes', () => {
      const names = new Set(pack.files.map((file) => file.path));
      for (const required of [
        'package.json', 'LICENSE', 'README.md', 'bin/comsol-workflow.mjs',
        'comsol_workflow/case.template.json', 'skills/comsol-multiphysics/SKILL.md',
        'skills/comsol-multiphysics/references/execution.md', 'templates/verification-plan.template.md',
        'scripts/install_skill.py', 'docs/approval-security.md',
        'examples/minimal-heat-plate/BuildHeatPlate.java',
        'examples/minimal-heat-plate/verified-results/metrics.csv',
      ]) {
        assert.ok(names.has(required), `Missing required packaged resource: ${required}`);
      }
      for (const name of names) {
        assert.ok(!/(^|\/)(?:\.git|\.venv|__pycache__|node_modules|private|approvals|runs)(?:\/|$)/i.test(name), name);
        assert.ok(!/(?:\.mph(?:bin)?|\.class|\.pyc|\.log|\.pem|\.key|\.receipt\.json|\.tgz)$/i.test(name), name);
        assert.ok(!/(^|\/)(?:\.npmrc|\.env(?:\..*)?)$/i.test(name), name);
      }
      const installedMetadata = JSON.parse(readFileSync(join(installed, 'package.json'), 'utf8'));
      for (const hook of ['preinstall', 'install', 'postinstall']) {
        assert.equal(installedMetadata.scripts?.[hook], undefined, `${hook} must not run during installation`);
      }
      assert.equal(Object.keys(installedMetadata.dependencies ?? {}).length, 0);
      for (const name of readdirSync(join(source, 'comsol_workflow')).filter((name) => /\.(py|json)$/.test(name))) {
        assert.deepEqual(readFileSync(join(installed, 'comsol_workflow', name)), readFileSync(join(source, 'comsol_workflow', name)), name);
      }
      const shim = join(install, 'node_modules', '.bin', process.platform === 'win32' ? 'comsol-workflow.cmd' : 'comsol-workflow');
      assert.ok(existsSync(shim), 'npm must create the executable entry point');
    });

    await t.test('installed version, resource location, and command help are available', () => {
      assert.equal(succeeded(cli(['--version'])).trim(), metadata.version);
      sameFile(succeeded(cli(['--package-root'])).trim(), installed);
      const help = succeeded(cli(['--help']));
      assert.match(help, /install-skill/);
      assert.match(help, /approval-keygen/);
      assert.match(help, /smoke/);
    });

    await t.test('caller cwd and PYTHONPATH cannot replace the bundled executor', () => {
      const hostile = join(scratch, 'hostile python path');
      for (const base of [caller, hostile]) {
        const fakeModule = join(base, 'comsol_workflow');
        mkdirSync(fakeModule, { recursive: true });
        writeFileSync(join(fakeModule, '__init__.py'), 'raise RuntimeError("UNTRUSTED_CALLER_MODULE_EXECUTED")\n');
        writeFileSync(join(fakeModule, '__main__.py'), 'raise RuntimeError("UNTRUSTED_CALLER_MODULE_EXECUTED")\n');
      }
      const result = cli(['init', '新建 case'], { env: { ...process.env, PYTHONPATH: hostile } });
      const created = JSON.parse(succeeded(result));
      sameFile(created.case, join(caller, '新建 case', 'case.json'));
      assert.equal(created.status, 'needs_engineering_input');
      assert.deepEqual(
        JSON.parse(readFileSync(created.case, 'utf8')),
        JSON.parse(readFileSync(join(installed, 'comsol_workflow', 'case.template.json'), 'utf8')),
      );
      assert.equal(cli(['init', '新建 case']).status, 2, 'Existing user cases must not be overwritten');
      assert.ok(!existsSync(join(installed, 'comsol_workflow', '__pycache__')), 'Execution should not mutate the installed code directory');
    });

    await t.test('CSV comparison preserves passing results and failure exit code', () => {
      const files = [join(installed, 'examples/offline/actual.csv'), join(installed, 'examples/offline/reference.csv')];
      const pass = JSON.parse(succeeded(cli(['compare', ...files, '--coordinate', 'time_s', '--atol', '0.01', '--rtol', '0.001'])));
      assert.equal(pass.passed, true);
      assert.equal(pass.rows, 3);
      const fail = cli(['compare', ...files, '--coordinate', 'time_s', '--atol', '0', '--rtol', '0']);
      assert.equal(fail.status, 2, fail.stderr);
      assert.equal(JSON.parse(fail.stdout).passed, false);
      assert.ok(JSON.parse(fail.stdout).failure_count > 0);
    });

    await t.test('an offline plan writes an explicitly unexecuted review bundle', () => {
      const result = JSON.parse(succeeded(cli([
        'plan', join(installed, 'examples/minimal-heat-plate/case.json'), '--out', '审阅 plan',
      ])));
      assert.equal(result.status, 'not_executed');
      assert.equal(result.checks.valid, false, 'Missing licensed model and installation must remain blocking');
      const runDirectory = join(caller, '审阅 plan');
      sameFile(result.run_dir, runDirectory);
      assert.match(readFileSync(join(runDirectory, 'REVIEW.md'), 'utf8'), /has not launched COMSOL/);
      const plan = JSON.parse(readFileSync(join(runDirectory, 'plan.json'), 'utf8'));
      assert.equal(plan.toolchain, null);
      assert.equal(plan.approval_public_key, null);
      for (const unexecuted of ['run-state.json', 'run.claim', 'results', 'completed.ok']) {
        assert.ok(!existsSync(join(runDirectory, unexecuted)), `Offline planning created execution artifact: ${unexecuted}`);
      }
    });

    await t.test('an unavailable explicitly selected Python fails instead of falling back', () => {
      const result = cli(['--help'], { env: { ...process.env, COMSOL_WORKFLOW_PYTHON: join(scratch, 'missing-python-executable') } });
      assert.equal(result.status, 1);
      assert.match(result.stderr, /Python 3\.10\+/);
      assert.match(result.stderr, /COMSOL_WORKFLOW_PYTHON/);
    });

    await t.test('all three client Skills install without overwriting an existing Skill', () => {
      const project = join(caller, '客户端 project');
      for (const [client, directory] of [['codex', '.agents'], ['claude', '.claude'], ['cursor', '.cursor']]) {
        succeeded(cli(['install-skill', '--client', client, '--project', project]));
        const target = join(project, directory, 'skills', 'comsol-multiphysics');
        assert.deepEqual(readFileSync(join(target, 'SKILL.md')), readFileSync(join(installed, 'skills/comsol-multiphysics/SKILL.md')));
        assert.ok(existsSync(join(target, 'references', 'execution.md')));
        writeFileSync(join(target, 'user-note.txt'), 'Keep this user file.');
        const repeated = cli(['install-skill', '--client', client, '--project', project]);
        assert.equal(repeated.status, 2);
        assert.match(repeated.stderr, /already exists/);
        assert.equal(readFileSync(join(target, 'user-note.txt'), 'utf8'), 'Keep this user file.');
      }
    });
  } finally {
    // Delete only the fresh, explicitly resolved temporary directory owned by this test.
    const temporaryRoot = realpathSync(tmpdir());
    const owned = relative(temporaryRoot, scratch);
    assert.ok(owned && !owned.startsWith('..') && !isAbsolute(owned));
    assert.match(owned, /^comsol-npm-test-/);
    rmSync(scratch, { recursive: true, force: true });
  }
});
