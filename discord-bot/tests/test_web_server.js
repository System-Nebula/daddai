/**
 * Test web server endpoints
 */
const http = require('http');

const MemoryService = require('../src/memoryService');
const DocumentService = require('../src/documentService');
const WebServer = require('../src/webServer');

console.log('=== Web Server Test ===\n');

const webServer = new WebServer(MemoryService, new DocumentService(), 3002); // Use test port

let testsPassed = 0;
let testsFailed = 0;

function makeRequest(path) {
    return new Promise((resolve, reject) => {
        const req = http.get(`http://localhost:3002${path}`, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                const contentType = res.headers['content-type'] || '';
                if (contentType.includes('application/json')) {
                    try {
                        resolve({ status: res.statusCode, data: JSON.parse(data), contentType });
                    } catch (e) {
                        resolve({ status: res.statusCode, data: data, contentType });
                    }
                } else {
                    resolve({ status: res.statusCode, data: data, contentType });
                }
            });
        });
        req.on('error', reject);
        req.setTimeout(5000, () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });
    });
}

async function testEndpoint(name, path, validator) {
    try {
        const result = await makeRequest(path);
        if (validator(result)) {
            console.log(`✓ ${name}`);
            testsPassed++;
        } else {
            console.error(`✗ ${name}: Validation failed`);
            testsFailed++;
        }
    } catch (error) {
        console.error(`✗ ${name}: ${error.message}`);
        testsFailed++;
    }
}

async function runTests() {
    // Start server
    await new Promise((resolve) => {
        webServer.start().then(() => {
            console.log('Web server started on port 3002\n');
            setTimeout(resolve, 1000); // Wait for server to be ready
        });
    });

    console.log('Testing endpoints...\n');

    // Test health endpoint
    await testEndpoint('Health check endpoint', '/api/health', (result) => {
        return result.status === 200 && result.data.status === 'ok';
    });

    // Test metrics endpoints
    await testEndpoint('Metrics JSON endpoint', '/api/metrics/json', (result) => {
        return result.status === 200 && result.data.requests && result.data.cache;
    });

    await testEndpoint('Metrics Prometheus endpoint', '/api/metrics/prometheus', (result) => {
        // Debug output
        if (result.status !== 200) {
            console.log(`  Debug: Status ${result.status}`);
            return false;
        }
        if (typeof result.data !== 'string') {
            console.log(`  Debug: Data type is ${typeof result.data}`);
            return false;
        }
        if (!result.data.includes('discord_bot_requests_total') && !result.data.includes('discord_bot_uptime')) {
            console.log(`  Debug: Data preview: ${result.data.substring(0, 200)}`);
            return false;
        }
        return result.status === 200 && typeof result.data === 'string';
    });

    // Test test endpoint
    await testEndpoint('Test endpoint', '/api/test', (result) => {
        return result.status === 200 && result.data.status === 'ok';
    });

    console.log('\n=== Web Server Test Summary ===');
    console.log(`Passed: ${testsPassed}`);
    console.log(`Failed: ${testsFailed}`);

    // Cleanup
    await webServer.stop();
    console.log('\nWeb server stopped.');

    if (testsFailed > 0) {
        process.exit(1);
    } else {
        console.log('\n✓ All web server tests passed!');
        process.exit(0);
    }
}

runTests().catch(error => {
    console.error('Test error:', error);
    process.exit(1);
});

