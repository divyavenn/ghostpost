/**
 * Simple test script to verify desktop app can communicate with backend
 */

const axios = require('axios');

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const USERNAME = process.env.USERNAME || 'divya_venn';

async function testBackendConnection() {
    console.log('Testing backend connection...\n');

    try {
        // Test health endpoint
        const health = await axios.get(`${BACKEND_URL}/health`);
        console.log('✅ Backend health check:', health.data);

        // Test getting pending jobs
        const jobs = await axios.get(`${BACKEND_URL}/desktop-jobs/${USERNAME}/pending`);
        console.log(`✅ Fetched pending jobs: ${jobs.data.length} jobs`);

        // Test job status
        const status = await axios.get(`${BACKEND_URL}/desktop-jobs/${USERNAME}/status`);
        console.log('✅ Job status:', status.data);

        console.log('\n✅ All tests passed! Desktop app can communicate with backend.');

    } catch (error) {
        console.error('\n❌ Test failed:', error.message);
        if (error.response) {
            console.error('Response status:', error.response.status);
            console.error('Response data:', error.response.data);
        }
        process.exit(1);
    }
}

testBackendConnection();
