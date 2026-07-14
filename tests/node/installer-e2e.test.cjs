const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const test = require('node:test');

const installers = [
  'npm/simplicio/install.js',
  'npm/simplicio-installer/install.js',
  'npm/simplicio-unscoped/install.js',
];

for (const relative of installers) {
  test(`${relative} executes its real CLI entrypoint without network in dry-run mode`, () => {
    const result = spawnSync(process.execPath, [path.resolve(relative)], {
      cwd: path.resolve('.'),
      env: { ...process.env, SIMPLICIO_INSTALL_DRY_RUN: '1' },
      encoding: 'utf8',
    });
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /\[DRY RUN\]/);
    assert.match(result.stdout, process.platform === 'win32' ? /powershell/ : /curl/);
  });
}
