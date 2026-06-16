#!/usr/bin/env node
const { execSync } = require('child_process');
const os = require('os');

const platform = os.platform();
const IS_WIN = platform === 'win32';

try {
  if (IS_WIN) {
    console.log('Downloading and running Simplicio installer for Windows...');
    execSync(
      'powershell -c "irm https://simpleti.com.br/simplicio/install.ps1 | iex"',
      { stdio: 'inherit' }
    );
  } else {
    console.log('Downloading and running Simplicio installer for macOS/Linux...');
    execSync(
      'curl -fsSL https://simpleti.com.br/simplicio/install.sh | sh',
      { stdio: 'inherit' }
    );
  }
  console.log('\n✅ Simplicio installed successfully!');
  console.log('   Run: simplicio chat');
  console.log('   Docs: https://simpleti.com.br/simplicio/#start');
} catch (err) {
  console.error('\n❌ Installation failed:', err.message);
  process.exit(1);
}
