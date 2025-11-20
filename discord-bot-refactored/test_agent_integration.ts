import refactoredAgentClient from './src/refactoredAgentClient.js';
import * as dotenv from 'dotenv';

dotenv.config();

async function testImageGeneration() {
    console.log('🧪 Testing Image Generation Tool Call...');
    try {
        // Wait a bit for servers to be fully ready
        await new Promise(resolve => setTimeout(resolve, 2000));

        const result = await refactoredAgentClient.runAgenticTask(
            "generate an image of a futuristic city with flying cars",
            {
                userId: 'test-user',
                channelId: 'test-channel',
                username: 'Tester',
                hasAttachments: false,
                isMentioned: true
            }
        );

        console.log('✅ Agent Task Result:', JSON.stringify(result, null, 2));

        if (result.tool_calls && result.tool_calls.length > 0) {
            const imgTool = result.tool_calls.find((tc: any) => tc.tool === 'generate_image');
            if (imgTool) {
                console.log('🎉 SUCCESS: Found generate_image tool call!');
                console.log('Tool Result:', imgTool.result);
            } else {
                console.log('⚠️ WARNING: tool_calls found but generate_image not present.');
            }
        } else {
            console.log('❌ FAILURE: No tool_calls returned.');
        }

    } catch (error) {
        console.error('❌ Error during test:', error);
    }
}

testImageGeneration();
