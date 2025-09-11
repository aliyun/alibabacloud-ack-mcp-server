#!/usr/bin/env python3
"""Check what SDK models are actually available."""

import sys
from alibabacloud_cs20151215 import models as cs20151215_models

def inspect_models():
    """Inspect available models in the CS SDK."""
    print("=== Available CS SDK Models ===")
    
    # Get all model classes
    model_classes = []
    for name in dir(cs20151215_models):
        if not name.startswith('_'):
            obj = getattr(cs20151215_models, name)
            if isinstance(obj, type):
                model_classes.append(name)
    
    # Filter for request models
    request_models = [name for name in model_classes if 'Request' in name]
    print(f"Found {len(request_models)} Request models:")
    
    addon_related = []
    for model in sorted(request_models):
        if 'addon' in model.lower() or 'Addon' in model:
            addon_related.append(model)
            print(f"  ✓ {model}")
        elif 'install' in model.lower() or 'Install' in model:
            addon_related.append(model)
            print(f"  ✓ {model}")
        elif 'uninstall' in model.lower() or 'UnInstall' in model:
            addon_related.append(model)
            print(f"  ✓ {model}")
        elif 'list' in model.lower() or 'List' in model:
            addon_related.append(model)
            print(f"  ✓ {model}")
        elif 'describe' in model.lower() or 'Describe' in model:
            addon_related.append(model)
            print(f"  ✓ {model}")
        elif 'modify' in model.lower() or 'Modify' in model:
            addon_related.append(model)
            print(f"  ✓ {model}")
        elif 'upgrade' in model.lower() or 'Upgrade' in model:
            addon_related.append(model)
            print(f"  ✓ {model}")
    
    print(f"\n=== {len(addon_related)} Addon-related Request Models ===")
    for model in sorted(addon_related):
        print(f"  {model}")
        
        # Try to inspect the model
        try:
            model_class = getattr(cs20151215_models, model)
            instance = model_class()
            print(f"    Created instance successfully")
            
            # Check common attributes
            attrs = dir(instance)
            relevant_attrs = [attr for attr in attrs if not attr.startswith('_') and not callable(getattr(instance, attr))]
            if relevant_attrs:
                print(f"    Attributes: {relevant_attrs[:10]}...")  # Show first 10
            
        except Exception as e:
            print(f"    Failed to create instance: {e}")
        print()

if __name__ == "__main__":
    inspect_models()