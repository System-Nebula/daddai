"""
Image Generation Tool - Generates images using RunPod API with FLUX GGUF models.
This tool allows the bot to generate images based on text prompts.
"""
import httpx
import base64
import json
import time
import os
import tempfile
import random
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
# FLUX GGUF model configuration
unet_model = os.getenv("RUNPOD_UNET_MODEL", "flux1-dev-Q8_0.gguf")
clip_model_1 = os.getenv("RUNPOD_CLIP_MODEL_1", "clip_l.safetensors")
clip_model_2 = os.getenv("RUNPOD_CLIP_MODEL_2", "t5xxl_fp8_e4m3fn.safetensors")
vae_model = os.getenv("RUNPOD_VAE_MODEL", "ae.safetensors")

if not api_key:
    logger.warning("RUNPOD_API_KEY not found in environment variables. Image generation will fail.")


def query_comfyui_models(comfyui_base_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Query ComfyUI API to get available models and node information.
    This helps diagnose what models are actually available on the server.
    
    Args:
        comfyui_base_url: Optional base URL for ComfyUI server (e.g., https://s3api-us-il-1.runpod.io/)
    
    Returns:
        Dict with available models and node information
    """
    if not api_key:
        return {
            "success": False,
            "error": "RUNPOD_API_KEY not configured"
        }
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Try multiple endpoints
        endpoints_to_try = []
        
        # Method 1: If custom ComfyUI URL provided
        if comfyui_base_url:
            base = comfyui_base_url.rstrip('/')
            endpoints_to_try.append({
                "name": "Custom ComfyUI URL",
                "object_info": f"{base}/object_info",
                "health": f"{base}/health"
            })
        
        # Method 2: RunPod API endpoint (standard ComfyUI template)
        runpod_base = f"https://api.runpod.ai/v2/{endpoint_id}"
        endpoints_to_try.append({
            "name": "RunPod API (standard)",
            "object_info": f"{runpod_base}/runsync",
            "health": f"{runpod_base}/health"
        })
        
        # Method 3: RunPod ComfyUI direct endpoint
        endpoints_to_try.append({
            "name": "RunPod ComfyUI direct",
            "object_info": f"{runpod_base}/comfyui/object_info",
            "health": f"{runpod_base}/comfyui/health"
        })
        
        # Method 4: Try RunPod S3 API (if endpoint_id maps to it)
        s3_base = f"https://s3api-us-il-1.runpod.io"
        endpoints_to_try.append({
            "name": "RunPod S3 API",
            "object_info": f"{s3_base}/object_info",
            "health": f"{s3_base}/health"
        })
        
        # Method 5: Try direct ComfyUI port (if exposed)
        # RunPod ComfyUI templates often expose on port 8188
        if comfyui_base_url:
            # Extract base without path to try port variations
            from urllib.parse import urlparse
            parsed = urlparse(comfyui_base_url)
            if parsed.netloc:
                base_host = parsed.scheme + "://" + parsed.netloc.split(':')[0]
                endpoints_to_try.append({
                    "name": "ComfyUI direct port 8188",
                    "object_info": f"{base_host}:8188/object_info",
                    "health": f"{base_host}:8188/system_stats"
                })
        
        for endpoint_config in endpoints_to_try:
            logger.info(f"Trying {endpoint_config['name']}...")
            
            # Try health check first
            try:
                with httpx.Client(timeout=10) as client:
                    health_response = client.get(endpoint_config["health"], headers=headers)
                    if health_response.status_code == 200:
                        logger.info(f"✅ Health check passed for {endpoint_config['name']}")
                        health_data = health_response.json()
                        logger.debug(f"Health data: {json.dumps(health_data, indent=2)}")
            except Exception as e:
                logger.debug(f"Health check failed for {endpoint_config['name']}: {e}")
            
            # Try object_info endpoint - RunPod might need POST with empty body
            try:
                with httpx.Client(timeout=10) as client:
                    # Try GET first
                    response = client.get(endpoint_config["object_info"], headers=headers)
                    
                    # If GET fails, try POST (some RunPod endpoints require POST)
                    if response.status_code != 200:
                        response = client.post(
                            endpoint_config["object_info"],
                            headers=headers,
                            json={}
                        )
                
                if response.status_code == 200:
                    object_info = response.json()
                    logger.info(f"✅ Successfully queried object_info from {endpoint_config['name']}")
                    
                    # Handle different response formats
                    # Sometimes RunPod wraps it, sometimes it's direct
                    if isinstance(object_info, dict) and "output" in object_info:
                        object_info = object_info["output"]
                    elif isinstance(object_info, dict) and "data" in object_info:
                        object_info = object_info["data"]
                    
                    # Extract UNET and CLIP loader information
                    result = {
                        "success": True,
                        "source": endpoint_config["name"],
                        "unet_loader": {},
                        "clip_loader": {},
                        "vae_loader": {},
                        "checkpoint_loader": {},
                        "all_nodes": list(object_info.keys()) if isinstance(object_info, dict) else [],
                        "loader_nodes": []
                    }
                    
                    if isinstance(object_info, dict):
                        # Check for UNETLoader
                        if "UNETLoader" in object_info:
                            result["unet_loader"] = object_info["UNETLoader"]
                            result["loader_nodes"].append("UNETLoader")
                            logger.info(f"UNETLoader found: {json.dumps(object_info['UNETLoader'], indent=2)}")
                        
                        # Check for CLIPLoader
                        if "CLIPLoader" in object_info:
                            result["clip_loader"] = object_info["CLIPLoader"]
                            result["loader_nodes"].append("CLIPLoader")
                            logger.info(f"CLIPLoader found: {json.dumps(object_info['CLIPLoader'], indent=2)}")
                        
                        # Check for VAELoader
                        if "VAELoader" in object_info:
                            result["vae_loader"] = object_info["VAELoader"]
                            result["loader_nodes"].append("VAELoader")
                            logger.info(f"VAELoader found: {json.dumps(object_info['VAELoader'], indent=2)}")
                        
                        # Check for CheckpointLoaderSimple (standard ComfyUI node)
                        if "CheckpointLoaderSimple" in object_info:
                            result["checkpoint_loader"] = object_info["CheckpointLoaderSimple"]
                            result["loader_nodes"].append("CheckpointLoaderSimple")
                            logger.info(f"CheckpointLoaderSimple found: {json.dumps(object_info['CheckpointLoaderSimple'], indent=2)}")
                        
                        # Find all loader-related nodes
                        loader_keywords = ["loader", "checkpoint", "unet", "clip", "vae", "model"]
                        for node_name in object_info.keys():
                            if any(keyword in node_name.lower() for keyword in loader_keywords):
                                if node_name not in result["loader_nodes"]:
                                    result["loader_nodes"].append(node_name)
                    
                    return result
                else:
                    logger.debug(f"Object info query returned status {response.status_code} for {endpoint_config['name']}: {response.text[:200]}")
            except Exception as e:
                logger.debug(f"Object info query failed for {endpoint_config['name']}: {e}")
                continue
        
        return {
            "success": False,
            "error": "Could not query ComfyUI API from any endpoint.",
            "note": "Tried multiple endpoints. You may need to check the ComfyUI web interface directly or use RunPod's console to see available models."
        }
        
    except Exception as e:
        logger.error(f"Error querying ComfyUI models: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def generate_image(
    prompt: str,
    negative_prompt: str = "blurry, low quality, distorted, realistic, photo, bad anatomy, worst quality, low quality, out of focus, soft focus, motion blur",
    width: int = 1024,
    height: int = 1024,
    steps: int = 10,
    cfg: float = 1.0,
    seed: Optional[int] = None,
    sampler_name: str = "euler",
    save_path: Optional[str] = None,
    guidance: float = 3.5
) -> Dict[str, Any]:
    """
    Generate an image using RunPod API with FLUX GGUF models.
    
    Args:
        prompt: Positive prompt describing what to generate
        negative_prompt: Negative prompt describing what to avoid (default: "blurry, low quality, distorted, realistic, photo, bad anatomy, worst quality, low quality, out of focus, soft focus, motion blur")
        width: Image width in pixels (default: 1024)
        height: Image height in pixels (default: 1024)
        steps: Number of sampling steps (default: 10)
        cfg: Classifier-free guidance scale (default: 1.0)
        seed: Random seed for reproducibility (default: None, uses random seed)
        sampler_name: Sampling method (default: "euler")
        save_path: Optional path to save the image file (default: None, saves to temp directory)
        guidance: FLUX guidance scale (default: 3.5)
        
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
        # API URL - use runsync endpoint for synchronous execution
        runsync_url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
        
        # Use provided seed or generate random seed
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        
        # Build the workflow payload - EXACT match to original working script
        workflow = {
            "input": {
                "workflow": {
                    "40": {
                        "inputs": {
                            "clip_name1": clip_model_1,
                            "clip_name2": clip_model_2,
                            "type": "flux"
                        },
                        "class_type": "DualCLIPLoader"
                    },
                    "47": {
                        "inputs": {
                            "unet_name": unet_model
                        },
                        "class_type": "UnetLoaderGGUF"
                    },
                    "vae_loader": {
                        "inputs": {
                            "vae_name": vae_model
                        },
                        "class_type": "VAELoader"
                    },
                    "6": {
                        "inputs": {
                            "text": prompt,
                            "clip": ["40", 0]
                        },
                        "class_type": "CLIPTextEncode"
                    },
                    "35": {
                        "inputs": {
                            "guidance": guidance,
                            "conditioning": ["6", 0]
                        },
                        "class_type": "FluxGuidance"
                    },
                    "33": {
                        "inputs": {
                            "text": negative_prompt,
                            "clip": ["40", 0]
                        },
                        "class_type": "CLIPTextEncode"
                    },
                    "27": {
                        "inputs": {
                            "width": width,
                            "height": height,
                            "batch_size": 1
                        },
                        "class_type": "EmptySD3LatentImage"
                    },
                    "31": {
                        "inputs": {
                            "seed": seed,
                            "steps": steps,
                            "cfg": int(cfg) if cfg == 1.0 else cfg,  # Ensure cfg=1 is sent as integer to match original script
                            "sampler_name": sampler_name,
                            "scheduler": "simple",
                            "denoise": 1,
                            "model": ["47", 0],
                            "positive": ["35", 0],
                            "negative": ["33", 0],
                            "latent_image": ["27", 0]
                        },
                        "class_type": "KSampler"
                    },
                    "8": {
                        "inputs": {
                            "samples": ["31", 0],
                            "vae": ["vae_loader", 0]
                        },
                        "class_type": "VAEDecode"
                    },
                    "9": {
                        "inputs": {
                            "filename_prefix": "ComfyUI",
                            "images": ["8", 0]
                        },
                        "class_type": "SaveImage"
                    }
                }
            }
        }
        
        # Send request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"🎨 Starting image generation with prompt: {prompt[:50]}...")
        logger.debug(f"Using UNET model: {unet_model}, CLIP models: {clip_model_1}, {clip_model_2}, VAE: {vae_model}")
        logger.debug(f"Settings: steps={steps}, cfg={cfg}, guidance={guidance}, size={width}x{height}, seed={seed}")
        
        # Log workflow structure for debugging (first 2000 chars)
        workflow_json = json.dumps(workflow, indent=2)
        logger.debug(f"Workflow JSON (first 2000 chars):\n{workflow_json[:2000]}")
        
        with httpx.Client(timeout=600) as client:
            response = client.post(runsync_url, headers=headers, json=workflow)
            
            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                logger.error(error_msg)
                logger.error(f"Workflow being sent uses UNET: {unet_model}, CLIP: {clip_model_1}, {clip_model_2}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
            result = response.json()
            job_id = result.get("id", "N/A")
            
            logger.info(f"✅ Job ID: {job_id}")
            
            # Check if job is still in queue/progress (runsync might return immediately)
            if result.get("status") in ["IN_QUEUE", "IN_PROGRESS"]:
                logger.info("Job is queued/running, polling for completion...")
                status_url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
                max_polls = 120
                poll_count = 0
                
                with httpx.Client(timeout=60) as status_client:
                    while poll_count < max_polls:
                        time.sleep(5)
                        status_response = status_client.get(status_url, headers=headers)
                        if status_response.status_code == 200:
                            result = status_response.json()
                            status = result.get('status', 'UNKNOWN')
                            if poll_count % 10 == 0:
                                logger.debug(f"Polling status: {status} (attempt {poll_count + 1})")
                            if status not in ["IN_QUEUE", "IN_PROGRESS"]:
                                break
                        poll_count += 1
        
        # Check for errors
        if "error" in result:
            error_msg = result["error"]
            logger.error(f"Job error: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "job_id": job_id
            }
        
        # Extract image data
        if "output" in result:
            output = result["output"]
            images = output.get("images", [])
            
            if not images:
                error_msg = "No images in job output"
                logger.error(error_msg)
                logger.debug(f"Full response: {json.dumps(result, indent=2)[:1000]}")
                return {
                    "success": False,
                    "error": error_msg,
                    "job_id": job_id
                }
            
            # Get first image
            image_data = images[0]
            img_type = image_data.get("type", "base64")
            data = image_data.get("data", "")
            filename = image_data.get("filename", "generated_image.png")
            
            if img_type == "base64":
                if not data:
                    error_msg = "No image data in response"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "job_id": job_id
                    }
                
                # Decode base64 image to verify it's valid
                try:
                    image_bytes = base64.b64decode(data)
                    image = Image.open(BytesIO(image_bytes))
                    
                    # Check if image is mostly white/blank
                    gray = image.convert('L')
                    avg_brightness = sum(gray.getdata()) / (gray.size[0] * gray.size[1])
                    
                    if avg_brightness > 240:
                        logger.warning(f"Image appears to be mostly white/blank (brightness: {avg_brightness:.1f}/255)")
                    
                    # Only save image if save_path is explicitly provided
                    image_path = None
                    if save_path:
                        image_path = save_path
                        image.save(image_path)
                        logger.info(f"💾 Image saved to: {image_path}")
                    else:
                        logger.info(f"✅ Image generated successfully (not saving to disk)")
                    
                    return {
                        "success": True,
                        "image_base64": data,  # Always include base64 for Discord attachment
                        "image_path": image_path,  # Only set if save_path was provided
                        "filename": filename,
                        "job_id": job_id,
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "width": width,
                        "height": height,
                        "steps": steps,
                        "cfg": cfg,
                        "seed": seed,
                        "guidance": guidance
                    }
                    
                except Exception as e:
                    error_msg = f"Error processing image data: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    return {
                        "success": False,
                        "error": error_msg,
                        "job_id": job_id
                    }
            elif img_type == "s3_url":
                logger.info(f"Image is at S3 URL: {data}")
                return {
                    "success": True,
                    "image_url": data,
                    "filename": filename,
                    "job_id": job_id,
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "width": width,
                    "height": height,
                    "steps": steps,
                    "cfg": cfg,
                    "seed": seed,
                    "guidance": guidance
                }
            else:
                error_msg = f"Unknown image type: {img_type}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "job_id": job_id
                }
        else:
            error_msg = "No output in response"
            logger.error(error_msg)
            logger.debug(f"Full response: {json.dumps(result, indent=2)[:1000]}")
            return {
                "success": False,
                "error": error_msg,
                "job_id": job_id
            }
        
    except httpx.TimeoutException:
        error_msg = "Request timed out. The API may be slow or unavailable."
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    except httpx.RequestError as e:
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

