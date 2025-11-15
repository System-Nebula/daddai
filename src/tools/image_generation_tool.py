"""
Image Generation Tool - Generates images using RunPod API with Stable Diffusion 1.5 + LoRA.
This tool allows the bot to generate images based on text prompts.
"""
import requests
import base64
import json
import time
import os
import tempfile
from typing import Dict, Any, Optional
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
from logger_config import logger

# Load environment variables
load_dotenv()

# Configuration
api_key = os.getenv("RUNPOD_API_KEY")
endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "a48mrbdsbzg35n")

if not api_key:
    logger.warning("RUNPOD_API_KEY not found in environment variables. Image generation will fail.")


def generate_image(
    prompt: str,
    negative_prompt: str = "bad hands, blurry, low quality, distorted",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg: float = 8.0,
    seed: Optional[int] = None,
    sampler_name: str = "euler",
    scheduler: str = "normal",
    lora_name: str = "epiNoiseoffset_v2.safetensors",
    lora_strength_model: float = 1.0,
    lora_strength_clip: float = 1.0,
    save_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate an image using RunPod API with Stable Diffusion 1.5 + LoRA.
    
    Args:
        prompt: Positive prompt describing what to generate
        negative_prompt: Negative prompt describing what to avoid (default: "bad hands, blurry, low quality, distorted")
        width: Image width in pixels (default: 512)
        height: Image height in pixels (default: 512)
        steps: Number of sampling steps (default: 20)
        cfg: Classifier-free guidance scale (default: 8.0)
        seed: Random seed for reproducibility (default: None, uses random seed)
        sampler_name: Sampling method (default: "euler")
        scheduler: Scheduler type (default: "normal")
        lora_name: LoRA model name (default: "epiNoiseoffset_v2.safetensors")
        lora_strength_model: LoRA strength for model (default: 1.0)
        lora_strength_clip: LoRA strength for CLIP (default: 1.0)
        save_path: Optional path to save the image file (default: None, saves to temp directory)
        
    Returns:
        Dict with:
        - success: bool
        - image_path: str (path to saved image file)
        - image_base64: str (base64 encoded image)
        - filename: str (generated filename)
        - job_id: str (RunPod job ID)
        - error: str (if error occurred)
    """
    if not api_key:
        return {
            "success": False,
            "error": "RUNPOD_API_KEY not configured. Please set it in your .env file."
        }
    
    try:
        # API URLs
        run_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
        status_url_template = f"https://api.runpod.ai/v2/{endpoint_id}/status/"
        
        # Use provided seed or generate random seed
        if seed is None:
            seed = int(time.time() * 1000) % (2**32)
        
        # Build the workflow payload
        workflow = {
            "input": {
                "workflow": {
                    "3": {
                        "inputs": {
                            "seed": seed,
                            "steps": steps,
                            "cfg": cfg,
                            "sampler_name": sampler_name,
                            "scheduler": scheduler,
                            "denoise": 1,
                            "model": ["10", 0],
                            "positive": ["6", 0],
                            "negative": ["7", 0],
                            "latent_image": ["5", 0]
                        },
                        "class_type": "KSampler",
                        "_meta": {
                            "title": "KSampler"
                        }
                    },
                    "4": {
                        "inputs": {
                            "ckpt_name": "v1-5-pruned-emaonly.ckpt"
                        },
                        "class_type": "CheckpointLoaderSimple",
                        "_meta": {
                            "title": "Load Checkpoint"
                        }
                    },
                    "5": {
                        "inputs": {
                            "width": width,
                            "height": height,
                            "batch_size": 1
                        },
                        "class_type": "EmptyLatentImage",
                        "_meta": {
                            "title": "Empty Latent Image"
                        }
                    },
                    "6": {
                        "inputs": {
                            "text": prompt,
                            "clip": ["10", 1]
                        },
                        "class_type": "CLIPTextEncode",
                        "_meta": {
                            "title": "CLIP Text Encode (Prompt)"
                        }
                    },
                    "7": {
                        "inputs": {
                            "text": negative_prompt,
                            "clip": ["10", 1]
                        },
                        "class_type": "CLIPTextEncode",
                        "_meta": {
                            "title": "CLIP Text Encode (Negative)"
                        }
                    },
                    "8": {
                        "inputs": {
                            "samples": ["3", 0],
                            "vae": ["4", 2]
                        },
                        "class_type": "VAEDecode",
                        "_meta": {
                            "title": "VAE Decode"
                        }
                    },
                    "9": {
                        "inputs": {
                            "filename_prefix": "ComfyUI_SD15",
                            "images": ["8", 0]
                        },
                        "class_type": "SaveImage",
                        "_meta": {
                            "title": "Save Image"
                        }
                    },
                    "10": {
                        "inputs": {
                            "lora_name": lora_name,
                            "strength_model": lora_strength_model,
                            "strength_clip": lora_strength_clip,
                            "model": ["4", 0],
                            "clip": ["4", 1]
                        },
                        "class_type": "LoraLoader",
                        "_meta": {
                            "title": "Load LoRA"
                        }
                    }
                }
            }
        }
        
        # Send initial request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"🎨 Starting image generation with prompt: {prompt[:50]}...")
        response = requests.post(run_url, headers=headers, json=workflow, timeout=30)
        
        if response.status_code != 200:
            error_msg = f"API request failed with status {response.status_code}: {response.text}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        response_data = response.json()
        job_id = response_data.get('id')
        
        if not job_id:
            error_msg = f"API response did not include a job ID. Response: {json.dumps(response_data, indent=2)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        logger.info(f"✅ Job started with ID: {job_id}")
        
        # Poll for job status
        status_url = status_url_template + job_id
        poll_count = 0
        max_polls = 120  # 10 minutes max (5 second intervals)
        
        while poll_count < max_polls:
            logger.debug(f"Polling job status... (attempt {poll_count + 1})")
            status_response = requests.get(status_url, headers=headers, timeout=30)
            status_data = status_response.json()
            job_status = status_data.get('status')
            
            if job_status == 'COMPLETED':
                logger.info("✅ Job completed successfully!")
                
                try:
                    # Extract image data
                    output = status_data.get('output', {})
                    images = output.get('images', [])
                    
                    if not images:
                        error_msg = "No images in job output"
                        logger.error(error_msg)
                        return {
                            "success": False,
                            "error": error_msg,
                            "job_id": job_id
                        }
                    
                    # Get first image
                    image_data = images[0]
                    image_base64 = image_data.get('data')
                    filename = image_data.get('filename', 'generated_image.png')
                    
                    if not image_base64:
                        error_msg = "No image data in response"
                        logger.error(error_msg)
                        return {
                            "success": False,
                            "error": error_msg,
                            "job_id": job_id
                        }
                    
                    # Decode base64 image to verify it's valid
                    image_bytes = base64.b64decode(image_base64)
                    image = Image.open(BytesIO(image_bytes))
                    
                    # Only save image if save_path is explicitly provided
                    image_path = None
                    if save_path:
                        image_path = save_path
                        image.save(image_path)
                        logger.info(f"💾 Image saved to: {image_path}")
                    else:
                        # Don't save to disk - just return base64 data
                        logger.info(f"✅ Image generated successfully (not saving to disk)")
                    
                    return {
                        "success": True,
                        "image_base64": image_base64,  # Always include base64 for Discord attachment
                        "image_path": image_path,  # Only set if save_path was provided
                        "filename": filename,
                        "job_id": job_id,
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "width": width,
                        "height": height,
                        "steps": steps,
                        "cfg": cfg,
                        "seed": seed
                    }
                    
                except (KeyError, IndexError, TypeError, Exception) as e:
                    error_msg = f"Error processing image data: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    
                    # Try to provide debug info
                    debug_data = json.loads(json.dumps(status_data))
                    try:
                        if 'output' in debug_data and 'images' in debug_data['output']:
                            for img in debug_data['output']['images']:
                                if 'data' in img:
                                    original_length = len(img['data'])
                                    img['data'] = f"<base64 data redacted, original length: {original_length}>"
                    except Exception:
                        pass
                    
                    logger.debug(f"Full response (redacted): {json.dumps(debug_data, indent=2)}")
                    
                    return {
                        "success": False,
                        "error": error_msg,
                        "job_id": job_id
                    }
            
            elif job_status in ['IN_QUEUE', 'IN_PROGRESS']:
                time.sleep(5)
                poll_count += 1
            else:
                error_msg = f"Job execution failed or was cancelled. Status: {job_status}"
                logger.error(error_msg)
                if 'error' in status_data:
                    error_msg += f" Error details: {status_data['error']}"
                
                return {
                    "success": False,
                    "error": error_msg,
                    "job_id": job_id,
                    "status": job_status
                }
        
        # Timeout
        error_msg = f"Job did not complete within expected time (max {max_polls * 5} seconds)"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "job_id": job_id
        }
        
    except requests.exceptions.Timeout:
        error_msg = "Request timed out. The API may be slow or unavailable."
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg
        }
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg
        }

