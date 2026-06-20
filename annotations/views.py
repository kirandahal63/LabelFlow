from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
import json
from django.db import transaction
from datasets.models import Dataset, Image
from projects.models import Project, ProjectMember
from .models import AnnotationTask, Annotation, Review
from accounts.models import User

BATCH_SIZE = 25


def get_project_initials(project_name):
    """Return uppercase initials from all words in project name (max 5 chars)."""
    words = [w for w in project_name.split() if w]
    return ''.join([w[0] for w in words]).upper()[:5]


# ─────────────────────────────────────────────────────────────
# BATCH ASSIGN (Admin → assigns CLS-SF-001 batches to annotator)
# ─────────────────────────────────────────────────────────────

@login_required
def batch_assign_view(request, project_id):
    """
    Admin assigns unassigned tasks to a specific annotator in groups of 25.
    Batch codes are generated as CLS-{INITIALS}-{NNN}, e.g. CLS-SF-001.
    """
    project = get_object_or_404(Project, id=project_id)
    if project.created_by != request.user and request.user.role != "admin":
        messages.error(request, "Only the project owner can assign tasks.")
        return redirect('project_detail', project_id=project.id)

    if request.method == 'POST':
        annotator_id = request.POST.get('annotator_id')
        dataset_id = request.POST.get('dataset_id', '')
        num_batches_str = request.POST.get('num_batches', '1')

        try:
            num_batches = max(1, int(num_batches_str))
        except ValueError:
            num_batches = 1

        if not annotator_id:
            messages.error(request, "Please select an annotator.")
            return redirect('project_detail', project_id=project.id)

        annotator = get_object_or_404(User, id=annotator_id)
        if not ProjectMember.objects.filter(
            project=project, user=annotator, role_in_project='annotator'
        ).exists():
            messages.error(request, "Selected user is not an annotator in this project.")
            return redirect('project_detail', project_id=project.id)

        tasks_qs = AnnotationTask.objects.filter(
            project=project, status='unassigned'
        ).order_by('created_at')
        if dataset_id:
            tasks_qs = tasks_qs.filter(image__dataset_id=dataset_id)

        tasks_to_assign = list(tasks_qs[: BATCH_SIZE * num_batches])

        if not tasks_to_assign:
            messages.warning(request, "No unassigned tasks found for the selected criteria.")
            return redirect('project_detail', project_id=project.id)

        initials = get_project_initials(project.name)

        # Count how many distinct batch codes already exist in this project
        existing_batch_count = (
            AnnotationTask.objects.filter(project=project)
            .exclude(batch__isnull=True)
            .exclude(batch='')
            .values('batch')
            .distinct()
            .count()
        )

        with transaction.atomic():
            assigned_count = 0
            batch_offset = 0
            for chunk_start in range(0, len(tasks_to_assign), BATCH_SIZE):
                chunk = tasks_to_assign[chunk_start : chunk_start + BATCH_SIZE]
                batch_num = existing_batch_count + batch_offset + 1
                batch_code = f"CLS-{initials}-{batch_num:03d}"
                batch_offset += 1

                for task in chunk:
                    task.assigned_to = annotator
                    task.status = 'assigned'
                    task.batch = batch_code
                    task.image.status = 'assigned'
                    task.save()
                    task.image.save()
                    assigned_count += 1

        messages.success(
            request,
            f"✅ Created {batch_offset} batch(es) — {assigned_count} tasks assigned to "
            f"{annotator.first_name} {annotator.last_name}.",
        )

    return redirect('project_detail', project_id=project.id)


# ─────────────────────────────────────────────────────────────
# LABEL / ANNOTATE TASK
# ─────────────────────────────────────────────────────────────

@login_required
def label_task_view(request, task_id):
    task = get_object_or_404(AnnotationTask, id=task_id)
    project = task.project

    is_owner = project.created_by == request.user
    is_assigned = task.assigned_to == request.user

    if not is_owner and not is_assigned:
        messages.error(request, "You are not authorized to access this labeling workspace.")
        return redirect('dashboard')

    annotation = Annotation.objects.filter(task=task).first()

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            labels = body.get('labels', [])
            notes = body.get('notes', '')

            with transaction.atomic():
                if not annotation:
                    annotation = Annotation(
                        task=task,
                        annotated_by=request.user,
                        labels=labels,
                        notes=notes,
                    )
                else:
                    annotation.labels = labels
                    annotation.notes = notes
                    annotation.version += 1

                annotation.status = 'draft'
                task.status = 'in_progress'
                task.image.status = 'assigned'

                annotation.save()
                task.save()
                task.image.save()

            # Navigate to next unannotated task within the same batch first
            next_task = None
            if task.batch:
                next_task = (
                    AnnotationTask.objects.filter(
                        batch=task.batch,
                        assigned_to=request.user,
                        status__in=['assigned', 'rejected'],
                    )
                    .exclude(id=task.id)
                    .order_by('created_at')
                    .first()
                )

            # Fall back to any other assigned task across other batches in this project
            if not next_task and not task.batch:
                next_task = (
                    AnnotationTask.objects.filter(
                        project=project,
                        assigned_to=request.user,
                        status__in=['assigned', 'in_progress', 'rejected'],
                    )
                    .exclude(id=task.id)
                    .order_by('created_at')
                    .first()
                )

            next_url = f"/annotations/task/{next_task.id}/" if next_task else None

            return JsonResponse({
                'status': 'success',
                'message': 'Annotation saved!',
                'next_task_url': next_url,
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # GET — compute batch-scoped progress
    if task.batch:
        total_in_batch = AnnotationTask.objects.filter(
            batch=task.batch, assigned_to=request.user
        ).count()
        annotated_in_batch = Annotation.objects.filter(
            task__batch=task.batch, task__assigned_to=request.user
        ).count()
    else:
        total_in_batch = AnnotationTask.objects.filter(
            project=project, assigned_to=request.user
        ).count()
        annotated_in_batch = Annotation.objects.filter(
            task__project=project, annotated_by=request.user
        ).count()

    context = {
        'task': task,
        'annotation': annotation,
        'label_set_json': json.dumps(project.label_set),
        'existing_labels_json': json.dumps(annotation.labels if annotation else []),
        'total_in_batch': total_in_batch,
        'annotated_in_batch': annotated_in_batch,
        'project': project,
        'batch_code': task.batch,
    }
    return render(request, 'annotations/label.html', context)


# ─────────────────────────────────────────────────────────────
# SUBMIT BATCH FOR REVIEW (Annotator)
# ─────────────────────────────────────────────────────────────

@login_required
def submit_batch_review_view(request, batch_code):
    """Submit entire batch for review — only allowed when ALL 25 tasks have annotations."""
    tasks = AnnotationTask.objects.filter(
        batch=batch_code, assigned_to=request.user
    ).select_related('image', 'project')

    if not tasks.exists():
        messages.warning(request, "No tasks found for this batch or not assigned to you.")
        return redirect('dashboard')

    project = tasks.first().project

    if request.method == 'POST':
        missing = []
        submitted_count = 0

        with transaction.atomic():
            for task in tasks:
                ann = Annotation.objects.filter(task=task).first()
                if not ann:
                    missing.append(task.image.filename)
                else:
                    if task.status not in ['approved', 'submitted']:
                        ann.status = 'submitted'
                        ann.save()
                        task.status = 'submitted'
                        task.image.status = 'annotated'
                        task.save()
                        task.image.save()
                        submitted_count += 1

        if missing:
            messages.warning(
                request,
                f"⚠️ Cannot submit batch '{batch_code}'. "
                f"{len(missing)} image(s) still need annotation. "
                "Please annotate all images before submitting.",
            )
        else:
            messages.success(
                request,
                f"✅ Batch '{batch_code}' submitted for review! ({submitted_count} tasks)",
            )

    return redirect('project_detail', project_id=project.id)


# ─────────────────────────────────────────────────────────────
# REVIEW SINGLE TASK (Reviewer — navigates within batch silently)
# ─────────────────────────────────────────────────────────────

@login_required
def review_task_view(request, task_id):
    task = get_object_or_404(AnnotationTask, id=task_id)
    project = task.project

    is_owner = project.created_by == request.user
    is_reviewer = ProjectMember.objects.filter(
        project=project, user=request.user, role_in_project='reviewer'
    ).exists()
    is_admin = request.user.role == "admin"

    if not is_owner and not is_reviewer and not is_admin:
        messages.error(request, "You are not authorized to review this task.")
        return redirect('dashboard')

    annotation = get_object_or_404(Annotation, task=task)

    if request.method == 'POST':
        is_json = request.content_type == 'application/json'
        
        if is_json:
            try:
                body = json.loads(request.body)
                decision = body.get('decision')
                comment = body.get('comment', '')
                labels = body.get('labels', annotation.labels)
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        else:
            decision = request.POST.get('decision')
            comment = request.POST.get('comment', '')
            labels = annotation.labels # Fallback

        if decision not in ['approved', 'rejected']:
            if is_json:
                return JsonResponse({'status': 'error', 'message': 'Invalid decision choice.'}, status=400)
            messages.error(request, "Invalid decision choice.")
            return redirect('review_task', task_id=task.id)

        with transaction.atomic():
            review, created = Review.objects.get_or_create(
                annotation=annotation,
                defaults={
                    'reviewed_by': request.user,
                    'decision': decision,
                    'comment': comment,
                },
            )
            if not created:
                review.reviewed_by = request.user
                review.decision = decision
                review.comment = comment
                review.save()

            annotation.status = decision
            annotation.labels = labels
            task.status = decision
            task.image.status = 'approved' if decision == 'approved' else 'rejected'
            annotation.save()
            task.save()
            task.image.save()

        next_url = f"/{project.id}/"

        # Silently move to next submitted task in same batch — no per-image notification
        if task.batch:
            next_task = (
                AnnotationTask.objects.filter(batch=task.batch, status='submitted')
                .exclude(id=task.id)
                .order_by('created_at')
                .first()
            )
            if next_task:
                next_url = f"/annotations/review/{next_task.id}/"
            else:
                # Entire batch reviewed — single summary message
                reviewed_count = AnnotationTask.objects.filter(
                    batch=task.batch, status__in=['approved', 'rejected']
                ).count()
                messages.success(
                    request,
                    f"✅ Batch '{task.batch}' review complete — {reviewed_count} task(s) reviewed.",
                )

        if is_json:
            return JsonResponse({'status': 'success', 'next_task_url': next_url})
        return redirect(next_url)

    # GET — build batch progress for review sidebar
    batch_total = 0
    batch_reviewed = 0
    if task.batch:
        batch_total = AnnotationTask.objects.filter(batch=task.batch).count()
        batch_reviewed = AnnotationTask.objects.filter(
            batch=task.batch, status__in=['approved', 'rejected']
        ).count()

    context = {
        'task': task,
        'annotation': annotation,
        'existing_labels_json': json.dumps(annotation.labels),
        'label_set_json': json.dumps(project.label_set),
        'project': project,
        'batch_total': batch_total,
        'batch_reviewed': batch_reviewed,
    }
    return render(request, 'annotations/review.html', context)


# ─────────────────────────────────────────────────────────────
# BATCH REVIEW LIST (Reviewer — overview of a batch)
# ─────────────────────────────────────────────────────────────

@login_required
def batch_review_list_view(request, batch_code):
    """Reviewer overview page for a batch — lists all tasks and starts review."""
    tasks = (
        AnnotationTask.objects.filter(batch=batch_code)
        .select_related('image', 'project', 'assigned_to')
        .order_by('created_at')
    )
    if not tasks.exists():
        messages.warning(request, "Batch not found.")
        return redirect('dashboard')

    project = tasks.first().project
    is_owner = project.created_by == request.user
    is_reviewer = ProjectMember.objects.filter(
        project=project, user=request.user, role_in_project='reviewer'
    ).exists()
    is_admin = request.user.role == "admin"

    if not is_owner and not is_reviewer and not is_admin:
        messages.error(request, "You are not authorized to review this batch.")
        return redirect('dashboard')

    first_task = tasks.filter(status='submitted').order_by('created_at').first()

    context = {
        'batch_code': batch_code,
        'tasks': tasks,
        'project': project,
        'first_task': first_task,
        'total': tasks.count(),
        'submitted': tasks.filter(status='submitted').count(),
        'approved': tasks.filter(status='approved').count(),
        'rejected': tasks.filter(status='rejected').count(),
    }
    return render(request, 'annotations/batch_review.html', context)
