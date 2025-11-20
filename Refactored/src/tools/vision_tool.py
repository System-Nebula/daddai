"""
Vision Tool - Process images for vision-capable LLMs.
Supports image analysis, OCR, and visual question answering.
Now async for better performance with HTTP requests.
"""
import base64
import io
import asyncio
from typing import Dict, Any, Optional, List
from PIL import Image
import httpx
from Refactored.logger_config import logger

class VisionTool:
    """
    Tool for processing images with vision-capable LLMs.
    """
    
    def __init__(self):
        """Initialize vision tool."""
        self.supported_formats = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']
        self._client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client
    
    async def process_image(self, image_url: str, question: Optional[str] = None) -> Dict[str, Any]:
        """
        Process an image asynchronously and return base64-encoded data and metadata.
        
        Args:
            image_url: URL or path to the image
            question: Optional question about the image
            
        Returns:
            Dict with image data, base64 encoding, and metadata
        """
        try:
            # Download image if it's a URL
            if image_url.startswith('http://') or image_url.startswith('https://'):
                client = await self._get_client()
                response = await client.get(image_url)
                response.raise_for_status()
                image_data = response.content
            else:
                # Assume it's a file path - read in thread pool
                loop = asyncio.get_event_loop()
                image_data = await loop.run_in_executor(
                    None,
                    lambda: open(image_url, 'rb').read()
                )
            
            # Open and process image in thread pool (PIL operations)
            loop = asyncio.get_event_loop()
            
            def process_image_sync():
                image = Image.open(io.BytesIO(image_data))
                
                # Convert to RGB if needed (for consistency)
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Resize if too large (max 2048x2048 for vision models)
                max_size = 2048
                if image.width > max_size or image.height > max_size:
                    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                    logger.info(f"Resized image from {image.width}x{image.height} to fit vision model limits")
                
                # Convert to base64
                buffer = io.BytesIO()
                image.save(buffer, format='PNG')
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                # Get metadata
                metadata = {
                    'width': image.width,
                    'height': image.height,
                    'format': image.format or 'PNG',
                    'mode': image.mode,
                    'size_bytes': len(image_data)
                }
                
                return image_base64, metadata
            
            image_base64, metadata = await loop.run_in_executor(None, process_image_sync)
            
            return {
                'success': True,
                'image_base64': image_base64,
                'metadata': metadata,
                'question': question
            }
            
        except Exception as e:
            logger.error(f"Error processing image: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def analyze_image(self, image_base64: str, question: str, llm_client=None) -> Dict[str, Any]:
        """
        Analyze an image using a vision-capable LLM.
        
        Args:
            image_base64: Base64-encoded image data
            question: Question about the image
            llm_client: LLM client with vision support
            
        Returns:
            Analysis result
        """
        if not llm_client:
            from src.clients.llm_client_factory import get_default_llm_client
            llm_client = get_default_llm_client()
        
        try:
            # Check if client supports vision
            if not hasattr(llm_client, 'supports_vision') or not llm_client.supports_vision():
                return {
                    'success': False,
                    'error': 'LLM client does not support vision'
                }
            
            # Create vision message
            messages = [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': question or 'What do you see in this image?'
                        },
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:image/png;base64,{image_base64}'
                            }
                        }
                    ]
                }
            ]
            
            # Generate response (check if client supports async)
            if hasattr(llm_client, 'generate_response_async'):
                response = await llm_client.generate_response_async(
                    messages=messages,
                    temperature=0.7,
                    max_tokens=500
                )
            else:
                # Fallback to sync in thread pool
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: llm_client.generate_response(
                        messages=messages,
                        temperature=0.7,
                        max_tokens=500
                    )
                )
            
            return {
                'success': True,
                'analysis': response if isinstance(response, str) else response.get('content', str(response)),
                'question': question
            }
            
        except Exception as e:
            logger.error(f"Error analyzing image: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get tool definition for LLM."""
        return {
            "name": "analyze_image",
            "description": "Analyze an image using vision capabilities. Use this when users send images or ask questions about images.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "URL or path to the image to analyze"
                    },
                    "question": {
                        "type": "string",
                        "description": "Question about the image (e.g., 'What is in this image?', 'Describe this image', 'What text is visible?')"
                    }
                },
                "required": ["image_url"]
            }
        }

