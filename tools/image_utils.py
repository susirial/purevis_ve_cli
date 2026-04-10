from PIL import Image
import os

def resize_and_compress_image(input_path: str, max_size_mb: float = 4.5, max_dimension: int = 1536) -> str:
    """
    Compress an image to ensure its base64 string doesn't break the API payload limit.
    Saves a compressed version if needed and returns the new path.
    """
    if not os.path.exists(input_path):
        return input_path
        
    file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    
    # 如果图片很小，直接返回原图
    if file_size_mb < 2.0:
        return input_path
        
    try:
        img = Image.open(input_path)
        
        # 转换 RGBA 为 RGB
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            
        # 调整尺寸
        width, height = img.size
        if width > max_dimension or height > max_dimension:
            ratio = min(max_dimension / width, max_dimension / height)
            new_size = (int(width * ratio), int(height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
        # 保存压缩后的版本
        dir_name = os.path.dirname(input_path)
        base_name = os.path.basename(input_path)
        name, _ = os.path.splitext(base_name)
        output_path = os.path.join(dir_name, f"{name}_compressed.jpg")
        
        img.save(output_path, "JPEG", quality=85, optimize=True)
        print(f"[Compress] Image compressed from {file_size_mb:.1f}MB to {os.path.getsize(output_path)/(1024*1024):.1f}MB")
        return output_path
        
    except Exception as e:
        print(f"[Warning] Failed to compress image {input_path}: {e}")
        return input_path