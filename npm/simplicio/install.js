#!/usr/bin/env node
const { execSync } = require('child_process');
const os = require('os');

function installerCommand(platform = os.platform()) {
  return platform === 'win32'
    ? 'powershell -c "irm https://simpleti.com.br/simplicio/install.ps1 | iex"'
    : 'curl -fsSL https://simpleti.com.br/simplicio/install.sh | sh';
}

function main({
  platform = os.platform(),
  execute = execSync,
  dryRun = process.env.SIMPLICIO_INSTALL_DRY_RUN === '1',
  log = console,
} = {}) {
  const command = installerCommand(platform);
  log.log(`Downloading and running Simplicio installer for ${platform === 'win32' ? 'Windows' : 'macOS/Linux'}...`);
  if (dryRun) {
    log.log(`[DRY RUN] ${command}`);
    return 0;
  }
  try {
    execute(command, { stdio: 'inherit' });
    log.log('\n✅ Simplicio installed successfully!');
    log.log('   Run: simplicio chat');
    log.log('   Docs: https://simpleti.com.br/simplicio/#start');
    return 0;
  } catch (err) {
    log.error('\n❌ Installation failed:', err.message);
    return 1;
  }
}

if (require.main === module) process.exitCode = main();

module.exports = { installerCommand, main };
