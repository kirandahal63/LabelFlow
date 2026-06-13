from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from datasets.models import Image
from projects.models import Project, ProjectMember
from .models import AnnotationTask, Annotation, Review
from accounts.models import User

@login_required
def assign_task_view(request, task_id):
    task = get_object_or_404(AnnotationTask, id=task_id)
    project = task.project
    
    if project.created_by != request.user:
        messages.error(request, "Only the project owner can assign tasks.")
        return redirect('project_detail', project_id=project.id)
        
    if request.method == 'POST':
        annotator_id = request.POST.get('annotator_id')
        
        with transaction.atomic():
            if annotator_id:
                annotator = get_object_or_404(User, id=annotator_id)
                # Verify that the annotator is a project member
                if not ProjectMember.objects.filter(project=project, user=annotator, role_in_project='annotator').exists():
                    messages.error(request, "Selected user is not an annotator in this project.")
                    return redirect('project_detail', project_id=project.id)
                    
                task.assigned_to = annotator
                task.status = 'assigned'
                task.image.status = 'assigned'
            else:
                task.assigned_to = None
                task.status = 'unassigned'
                task.image.status = 'pending'
                
            task.save()
            task.image.save()
            messages.success(request, f"Updated assignment for task: {task.image.filename}")
            
    return redirect('project_detail', project_id=project.id)

@login_required
def auto_assign_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if project.created_by != request.user:
        messages.error(request, "Only the project owner can auto-assign tasks.")
        return redirect('project_detail', project_id=project.id)
        
    if request.method == 'POST':
        # Get all annotators for this project
        annotator_members = ProjectMember.objects.filter(project=project, role_in_project='annotator').select_related('user')
        annotators = [m.user for m in annotator_members]
        
        if not annotators:
            messages.error(request, "There are no annotators in this project to assign tasks to.")
            return redirect('project_detail', project_id=project.id)
            
        # Get all unassigned tasks
        unassigned_tasks = AnnotationTask.objects.filter(project=project, status='unassigned').select_related('image')
        
        if not unassigned_tasks:
            messages.warning(request, "There are no unassigned tasks in this project.")
            return redirect('project_detail', project_id=project.id)
            
        # Distribute tasks evenly
        with transaction.atomic():
            assigned_count = 0
            for idx, task in enumerate(unassigned_tasks):
                assigned_user = annotators[idx % len(annotators)]
                task.assigned_to = assigned_user
                task.status = 'assigned'
                task.image.status = 'assigned'
                task.save()
                task.image.save()
                assigned_count += 1
                
            messages.success(request, f"Auto-assigned {assigned_count} tasks evenly among {len(annotators)} annotators.")
            
    return redirect('project_detail', project_id=project.id)

@login_required
def label_task_view(request, task_id):
    task = get_object_or_404(AnnotationTask, id=task_id)
    project = task.project
    
    # Authorize annotator or owner
    is_owner = (project.created_by == request.user)
    is_assigned = (task.assigned_to == request.user)
    
    if not is_owner and not is_assigned:
        messages.error(request, "You are not authorized to access this labeling workspace.")
        return redirect('dashboard')
        
    # Get existing annotation draft or submitted annotation
    annotation = Annotation.objects.filter(task=task).first()
    
    if request.method == 'POST':
        # Accept JSON payloads for save/submit actions
        try:
            body = json.loads(request.body)
            labels = body.get('labels', [])
            notes = body.get('notes', '')
            action = body.get('action', 'save') # 'save' (draft) or 'submit'
            
            with transaction.atomic():
                if not annotation:
                    annotation = Annotation(
                        task=task,
                        annotated_by=request.user,
                        labels=labels,
                        notes=notes
                    )
                else:
                    annotation.labels = labels
                    annotation.notes = notes
                    annotation.version += 1
                    
                if action == 'submit':
                    annotation.status = 'submitted'
                    task.status = 'submitted'
                    task.image.status = 'annotated'
                else:
                    annotation.status = 'draft'
                    task.status = 'in_progress'
                    task.image.status = 'assigned'
                    
                annotation.save()
                task.save()
                task.image.save()
                
            return JsonResponse({'status': 'success', 'message': f"Annotation {action}d successfully."})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    # GET Request: Render the workspace
    context = {
        'task': task,
        'annotation': annotation,
        'label_set_json': json.dumps(project.label_set),
        'existing_labels_json': json.dumps(annotation.labels if annotation else []),
    }
    return render(request, 'annotations/label.html', context)

@login_required
def review_task_view(request, task_id):
    task = get_object_or_404(AnnotationTask, id=task_id)
    project = task.project
    
    # Authorize reviewer or project owner
    is_owner = (project.created_by == request.user)
    is_reviewer = ProjectMember.objects.filter(project=project, user=request.user, role_in_project='reviewer').exists()
    
    if not is_owner and not is_reviewer:
        messages.error(request, "You are not authorized to review this task.")
        return redirect('dashboard')
        
    annotation = get_object_or_404(Annotation, task=task)
    
    if request.method == 'POST':
        decision = request.POST.get('decision') # 'approved' or 'rejected'
        comment = request.POST.get('comment', '')
        
        if decision not in ['approved', 'rejected']:
            messages.error(request, "Invalid decision choice.")
            return redirect('review_task', task_id=task.id)
            
        with transaction.atomic():
            # Create or update Review
            review, created = Review.objects.get_or_create(
                annotation=annotation,
                defaults={'reviewed_by': request.user, 'decision': decision, 'comment': comment}
            )
            if not created:
                review.reviewed_by = request.user
                review.decision = decision
                review.comment = comment
                review.save()
                
            # Update annotation, task, and image status
            annotation.status = decision
            task.status = decision
            
            if decision == 'approved':
                task.image.status = 'approved'
            else:
                task.image.status = 'rejected'
                
            annotation.save()
            task.save()
            task.image.save()
            
            messages.success(request, f"Task '{task.image.filename}' has been {decision}.")
            return redirect('dashboard')
            
    # GET Request: render review panel
    context = {
        'task': task,
        'annotation': annotation,
        'existing_labels_json': json.dumps(annotation.labels),
    }
    return render(request, 'annotations/review.html', context)

@login_required
def bulk_assign_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if project.created_by != request.user:
        messages.error(request, "Only the project owner can assign tasks.")
        return redirect('project_detail', project_id=project.id)
        
    if request.method == 'POST':
        annotator_id = request.POST.get('annotator_id')
        num_tasks_str = request.POST.get('num_tasks', '0')
        dataset_id = request.POST.get('dataset_id')
        
        try:
            num_tasks = int(num_tasks_str)
        except ValueError:
            num_tasks = 0
            
        if not annotator_id or num_tasks <= 0:
            messages.error(request, "Invalid annotator selection or number of images.")
            return redirect('project_detail', project_id=project.id)
            
        annotator = get_object_or_404(User, id=annotator_id)
        
        # Verify annotator is project member
        if not ProjectMember.objects.filter(project=project, user=annotator, role_in_project='annotator').exists():
            messages.error(request, "User is not an annotator in this project.")
            return redirect('project_detail', project_id=project.id)
            
        # Get unassigned tasks
        tasks = AnnotationTask.objects.filter(project=project, status='unassigned')
        if dataset_id:
            tasks = tasks.filter(image__dataset_id=dataset_id)
            
        tasks = list(tasks[:num_tasks])
        
        assigned_count = 0
        with transaction.atomic():
            for task in tasks:
                task.assigned_to = annotator
                task.status = 'assigned'
                task.image.status = 'assigned'
                task.save()
                task.image.save()
                assigned_count += 1
                
        if assigned_count > 0:
            messages.success(request, f"Successfully assigned {assigned_count} tasks to {annotator.email}.")
        else:
            messages.warning(request, "No unassigned tasks matching your criteria were found.")
            
    return redirect('project_detail', project_id=project.id)
