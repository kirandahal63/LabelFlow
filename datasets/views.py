from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
import os
import posixpath
import zipfile
import hashlib
from PIL import Image as PILImage
from pathlib import Path
from projects.models import Project
from .models import Dataset, Image
from annotations.models import AnnotationTask

@login_required
def upload_dataset_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    # Verify authorization (only creator or admin can upload)
    if project.created_by != request.user and request.user.role != "admin":
        messages.error(request, "Only the project owner or admins can upload datasets.")
        return redirect('project_detail', project_id=project.id)
        
    if request.method == 'POST':
        name = request.POST.get('name')
        zip_file = request.FILES.get('zip_file')
        
        if not name or not zip_file:
            messages.error(request, "Please provide a name and a zip archive.")
            return redirect('project_detail', project_id=project.id)
            
        # Create dataset record
        dataset = Dataset.objects.create(
            project=project,
            name=name,
            original_filename=zip_file.name,
            uploaded_by=request.user,
            status='processing'
        )
        
        # Define extraction target
        target_dir = Path(settings.MEDIA_ROOT) / 'datasets' / str(dataset.id)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            total_images_count = 0
            
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    # Security check: Skip directories and check for Zip Slip
                    filename = os.path.basename(member)
                    if not filename:
                        continue
                        
                    # Target path safety check (avoid directory traversal)
                    target_path = Path(os.path.abspath(target_dir / member))
                    if not str(target_path).startswith(str(os.path.abspath(target_dir))):
                        # Attempted directory traversal, skip
                        continue
                        
                    # Filter for image files
                    ext = target_path.suffix.lower()
                    if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
                        continue
                        
                    # Ensure parent dir exists (if zip has folders)
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Extract file data
                    data = zip_ref.read(member)
                    
                    # Compute MD5 checksum
                    md5_hash = hashlib.md5(data).hexdigest()
                    
                    # Check unique together constraint for (dataset, md5_hash)
                    if Image.objects.filter(dataset=dataset, md5_hash=md5_hash).exists():
                        # Skip duplicate image in same dataset
                        continue
                        
                    # Write file temporarily or permanently
                    with open(target_path, 'wb') as f:
                        f.write(data)
                        
                    # Open with Pillow to get dimensions and verify image integrity
                    try:
                        with PILImage.open(target_path) as img:
                            width, height = img.size
                    except Exception as e:
                        # Corrupted image or invalid format, remove and skip
                        if target_path.exists():
                            os.remove(target_path)
                        continue
                        
                    # Create Image record — build URL as posix path relative to MEDIA_ROOT
                    relative_path = target_path.relative_to(Path(settings.MEDIA_ROOT))
                    storage_url = posixpath.join(settings.MEDIA_URL, *relative_path.parts)
                    
                    image_record = Image.objects.create(
                        dataset=dataset,
                        filename=filename,
                        storage_url=storage_url,
                        file_size_bytes=len(data),
                        width_px=width,
                        height_px=height,
                        md5_hash=md5_hash,
                        status='pending'
                    )
                    
                    # Create Annotation Task
                    AnnotationTask.objects.create(
                        image=image_record,
                        project=project,
                        status='unassigned'
                    )
                    
                    total_images_count += 1
            
            # Update dataset status
            dataset.total_images = total_images_count
            dataset.status = 'ready' if total_images_count > 0 else 'error'
            dataset.save()
            
            if total_images_count > 0:
                messages.success(request, f"Successfully processed dataset '{name}' and generated {total_images_count} tasks!")
            else:
                messages.warning(request, f"Dataset uploaded but no valid images were found.")
                
        except Exception as e:
            dataset.status = 'error'
            dataset.save()
            messages.error(request, f"Error processing zip file: {str(e)}")
            
    return redirect('project_detail', project_id=project.id)
