const assert = require('node:assert/strict');
const test = require('node:test');

const modules = [
  '../../npm/simplicio/install.js',
  '../../npm/simplicio-installer/install.js',
  '../../npm/simplicio-unscoped/install.js',
];

function logger() {
  const messages = [];
  return {
    messages,
    log: { log: (...parts) => messages.push(parts.join(' ')), error: (...parts) => messages.push(parts.join(' ')) },
  };
}

for (const path of modules) {
  const installer = require(path);

  test(`${path} routes Windows and Unix installers`, () => {
    assert.match(installer.installerCommand('win32'), /powershell.*install\.ps1/);
    assert.match(installer.installerCommand('linux'), /curl.*install\.sh/);
    assert.match(installer.installerCommand('darwin'), /curl.*install\.sh/);
  });

  test(`${path} dry-run never executes`, () => {
    const capture = logger();
    const code = installer.main({
      platform: 'linux',
      dryRun: true,
      execute: () => assert.fail('execute must not run'),
      log: capture.log,
    });
    assert.equal(code, 0);
    assert.ok(capture.messages.some((line) => line.includes('[DRY RUN]')));
  });

  test(`${path} returns success after execution`, () => {
    const capture = logger();
    let command;
    const code = installer.main({
      platform: 'win32',
      dryRun: false,
      execute: (value) => { command = value; },
      log: capture.log,
    });
    assert.equal(code, 0);
    assert.match(command, /powershell/);
  });

  test(`${path} converts execution errors into a non-zero result`, () => {
    const capture = logger();
    const code = installer.main({
      platform: 'linux',
      dryRun: false,
      execute: () => { throw new Error('synthetic failure'); },
      log: capture.log,
    });
    assert.equal(code, 1);
    assert.ok(capture.messages.some((line) => line.includes('synthetic failure')));
  });
}
