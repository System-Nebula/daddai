#!/usr/bin/env python3
"""
Script to query ComfyUI API and check available models.
This helps diagnose what models are actually available on the RunPod server.
"""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.tools.image_generation_tool import query_comfyui_models
from logger_config import logger

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Query ComfyUI API for available models")
    parser.add_argument(
        "--comfyui-url",
        type=str,
        default=None,
        help="ComfyUI base URL (e.g., https://s3api-us-il-1.runpod.io/)"
    )
    args = parser.parse_args()
    
    print("🔍 Querying ComfyUI API for available models...")
    if args.comfyui_url:
        print(f"Using custom ComfyUI URL: {args.comfyui_url}")
    print("=" * 60)
    
    result = query_comfyui_models(comfyui_base_url=args.comfyui_url)
    
    print("\n📊 Results:")
    print(json.dumps(result, indent=2))
    
    if result.get("success"):
        print("\n✅ Successfully queried ComfyUI API!")
        
        if result.get("unet_loader"):
            print("\n📦 UNETLoader node found:")
            unet_info = result["unet_loader"]
            if "input" in unet_info and "required" in unet_info["input"]:
                if "unet_name" in unet_info["input"]["required"]:
                    unet_config = unet_info["input"]["required"]["unet_name"]
                    if isinstance(unet_config, list) and len(unet_config) > 0:
                        print(f"   Available UNET models: {unet_config[0]}")
                    else:
                        print(f"   UNET config: {unet_config}")
        
        if result.get("clip_loader"):
            print("\n📦 CLIPLoader node found:")
            clip_info = result["clip_loader"]
            if "input" in clip_info and "required" in clip_info["input"]:
                if "clip_name" in clip_info["input"]["required"]:
                    clip_config = clip_info["input"]["required"]["clip_name"]
                    if isinstance(clip_config, list) and len(clip_config) > 0:
                        print(f"   Available CLIP models: {clip_config[0]}")
                    else:
                        print(f"   CLIP config: {clip_config}")
        
        if result.get("vae_loader"):
            print("\n📦 VAELoader node found:")
            vae_info = result["vae_loader"]
            if "input" in vae_info and "required" in vae_info["input"]:
                if "vae_name" in vae_info["input"]["required"]:
                    vae_config = vae_info["input"]["required"]["vae_name"]
                    if isinstance(vae_config, list) and len(vae_config) > 0:
                        print(f"   Available VAE models: {vae_config[0]}")
                    else:
                        print(f"   VAE config: {vae_config}")
    else:
        print(f"\n❌ Failed to query API: {result.get('error', 'Unknown error')}")
        if "note" in result:
            print(f"\n💡 {result['note']}")

if __name__ == "__main__":
    main()

