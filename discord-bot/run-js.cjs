// Wrapper script to run CommonJS version
// This temporarily removes "type": "module" from package.json to allow CommonJS files

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const packageJsonPath = path.join(__dirname, 'package.json');
const packageJsonBackup = path.join(__dirname, 'package.json.backup');

// Read package.json
const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));

// Backup original
fs.writeFileSync(packageJsonBackup, JSON.stringify(packageJson, null, 2));

// Remove "type": "module" temporarily
delete packageJson.type;

// Write modified package.json
fs.writeFileSync(packageJsonPath, JSON.stringify(packageJson, null, 2));

// Run index.cjs
const child = spawn('node', ['index.cjs'], {
    stdio: 'inherit',
    shell: true,
    cwd: __dirname
});

// Restore package.json on exit
const restore = () => {
    if (fs.existsSync(packageJsonBackup)) {
        fs.copyFileSync(packageJsonBackup, packageJsonPath);
        fs.unlinkSync(packageJsonBackup);
    }
};

child.on('exit', (code) => {
    restore();
    process.exit(code || 0);
});

process.on('SIGINT', () => {
    restore();
    child.kill('SIGINT');
});

process.on('SIGTERM', () => {
    restore();
    child.kill('SIGTERM');
});

