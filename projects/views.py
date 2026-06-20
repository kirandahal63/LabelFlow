from urllib import request

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django import forms
from django.db.models import Count, Q
from .models import Project, ProjectMember
from accounts.models import User
from datasets.models import Dataset
from annotations.models import AnnotationTask, Annotation


# ─────────────────────────────────────────────────────────────
# PROJECT FORM
# ─────────────────────────────────────────────────────────────

class ProjectForm(forms.ModelForm):
    labels_raw = forms.CharField(
        max_length=1000,
        widget=forms.TextInput(attrs={'placeholder': 'car, person, traffic light, dog'}),
        help_text="Enter labels separated by commas",
    )

    class Meta:
        model = Project
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Describe the goal of this annotation project...'}
            ),
        }


# ─────────────────────────────────────────────────────────────
# DASHBOARD (Annotator / Reviewer)
# ─────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    user = request.user

    if user.role == 'admin':
        return redirect('admin_dashboard')

    # Projects this user is a member of (with role)
    member_project_entries = (
        ProjectMember.objects.filter(user=user)
        .select_related('project')
        .order_by('-joined_at')
    )

    # ── ANNOTATOR: batches assigned to this user ──
    annotator_batch_codes = (
        AnnotationTask.objects.filter(assigned_to=user)
        .exclude(batch__isnull=True)
        .exclude(batch='')
        .values_list('batch', flat=True)
        .distinct()
        .order_by('batch')
    )

    my_batches = []
    for batch_code in annotator_batch_codes:
        batch_tasks = AnnotationTask.objects.filter(
            batch=batch_code, assigned_to=user
        ).select_related('project', 'image')
        if not batch_tasks.exists():
            continue
        project = batch_tasks.first().project
        total = batch_tasks.count()
        annotated = Annotation.objects.filter(task__in=batch_tasks).count()
        all_annotated = annotated >= total
        is_fully_submitted = batch_tasks.filter(
            status__in=['submitted', 'approved']
        ).count() == total
        # First task to continue annotating
        first_task = (
            batch_tasks.filter(status='rejected').order_by('created_at').first()
            or batch_tasks.filter(status='assigned').order_by('created_at').first()
            or batch_tasks.filter(status='in_progress').order_by('created_at').first()
            or batch_tasks.order_by('created_at').first()
        )
        my_batches.append({
            'code': batch_code,
            'project': project,
            'total': total,
            'annotated': annotated,
            'all_annotated': all_annotated,
            'is_fully_submitted': is_fully_submitted,
            'first_task': first_task,
        })

    # ── REVIEWER: submitted batches in their assigned projects ──
    reviewer_project_ids = list(
        ProjectMember.objects.filter(user=user, role_in_project='reviewer').values_list('project_id', flat=True)
    )

    reviewer_batches = []
    if reviewer_project_ids:
        reviewer_batch_codes = (
            AnnotationTask.objects.filter(
                project_id__in=reviewer_project_ids,
                status='submitted',
            )
            .exclude(batch__isnull=True)
            .values_list('batch', flat=True)
            .distinct()
            .order_by('batch')
        )
        for batch_code in reviewer_batch_codes:
            batch_tasks = AnnotationTask.objects.filter(batch=batch_code).select_related('project', 'assigned_to')
            if not batch_tasks.exists():
                continue
            project = batch_tasks.first().project
            assigned_to = batch_tasks.first().assigned_to
            total = batch_tasks.count()
            submitted = batch_tasks.filter(status='submitted').count()
            approved = batch_tasks.filter(status='approved').count()
            rejected = batch_tasks.filter(status='rejected').count()
            first_submitted = (
                batch_tasks.filter(status='submitted').order_by('created_at').first()
            )
            reviewer_batches.append({
                'code': batch_code,
                'project': project,
                'assigned_to': assigned_to,
                'total': total,
                'submitted': submitted,
                'approved': approved,
                'rejected': rejected,
                'first_task': first_submitted,
            })

    context = {
        'member_project_entries': member_project_entries,
        'member_projects_count': member_project_entries.count(),
        'my_batches': my_batches,
        'reviewer_batches': reviewer_batches,
    }
    return render(request, 'dashboard.html', context)


# ─────────────────────────────────────────────────────────────
# ADMIN DASHBOARD
# ─────────────────────────────────────────────────────────────

@login_required
def admin_dashboard_view(request):

    # Count unique users who are reviewers in any project
    total_unique_reviewers = ProjectMember.objects.filter(
        role_in_project='reviewer'
    ).values('user').distinct().count()
    total_unique_annotators = ProjectMember.objects.filter(
        role_in_project='annotator'
    ).values('user').distinct().count()

    """Admin-only dashboard with sidenav, project management, profile and review stats."""
    if request.user.role != 'admin':
        messages.error(request, "Admin access required.")
        return redirect('dashboard')

    all_projects = Project.objects.all().select_related('created_by').order_by('-created_at')

    annotator_stats = (Annotation.objects.values(
            'annotated_by__id',
            'annotated_by__first_name',
            'annotated_by__last_name',
            'annotated_by__email',
        )
        .annotate(
            total_annotations=Count('id'),
            approved_annotations=Count('id', filter=Q(status='approved')),
            submitted_annotations=Count('id', filter=Q(status='submitted')),
            rejected_annotations=Count('id', filter=Q(status='rejected')),
        )
        .order_by('-total_annotations')
    )

    project_review_stats = []
    for project in all_projects:
        tasks = AnnotationTask.objects.filter(project=project)
        total = tasks.count()
        approved = tasks.filter(status='approved').count()
        submitted = tasks.filter(status='submitted').count()
        in_progress = tasks.filter(status='in_progress').count()
        unassigned = tasks.filter(status='unassigned').count()
        rejected = tasks.filter(status='rejected').count()

        annotators_in_project = ProjectMember.objects.filter(
            project=project, role_in_project='annotator'
        ).select_related('user')

        annotator_breakdown = []
        for member in annotators_in_project:
            done = Annotation.objects.filter(
                task__project=project, annotated_by=member.user
            ).count()
            annotator_breakdown.append({'user': member.user, 'annotations_done': done})

        project_review_stats.append({
            'project': project,
            'total': total,
            'approved': approved,
            'submitted': submitted,
            'in_progress': in_progress,
            'unassigned': unassigned,
            'rejected': rejected,
            'progress_pct': round((approved / total * 100) if total > 0 else 0),
            'annotator_breakdown': annotator_breakdown,
        })

    all_users = User.objects.all().order_by('first_name', 'last_name')

    context = {
        'all_projects': all_projects,
        'all_projects_count': all_projects.count(),
        'project_review_stats': project_review_stats,
        'annotator_stats': annotator_stats,
        'total_unique_reviewers': total_unique_reviewers,
        'total_unique_annotators': total_unique_annotators,
        'all_users': all_users,
        'all_users_count': all_users.count(),
        'active_tab': request.GET.get('tab', 'projects'),
    }
    return render(request, 'admin_dashboard.html', context)


# ─────────────────────────────────────────────────────────────
# PROJECT CREATE
# ─────────────────────────────────────────────────────────────

@login_required
def project_create_view(request):
    if request.user.role != "admin":
        return redirect("no_access")
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            labels_raw = form.cleaned_data['labels_raw']
            labels_list = [label.strip() for label in labels_raw.split(',') if label.strip()]
            project.label_set = labels_list
            project.status = 'active'
            project.save()
            messages.success(request, f"Project '{project.name}' created successfully!")
            return redirect('project_detail', project_id=project.id)
    else:
        form = ProjectForm()
    return render(request, 'projects/create.html', {'form': form})


# ─────────────────────────────────────────────────────────────
# PROJECT DETAIL (role-scoped)
# ─────────────────────────────────────────────────────────────

@login_required

def update_project_status(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    user = request.user

    is_creator = project.created_by == user
    membership = ProjectMember.objects.filter(project=project, user=user).first()

    # 1. FIX: Only return if authorized check fails
    if not is_creator and not membership:
        messages.error(request, "You are not authorized to view this project.")
        return redirect('dashboard')

    # 2. Proceed with authorized logic
    role = "owner" if is_creator else (membership.role_in_project if membership else None)
    is_admin_user = (user.role == 'admin')

    if role == 'owner' or is_admin_user:
        if request.method == 'POST':
            new_status = request.POST.get('status')
            valid_statuses = ['draft', 'active', 'in_review', 'completed', 'archived']
            
            if new_status in valid_statuses:
                project.status = new_status
                project.save()
                messages.success(request, f"Project status updated to {new_status.replace('_', ' ').title()}.")
            else:
                messages.error(request, "Invalid status selected.")
        
        # 3. Always return to the project detail page
        return redirect('project_detail', project_id=project_id)

    # Fallback if user somehow reaches here without owner/admin rights
    return redirect('dashboard')


@login_required
def project_detail_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    user = request.user

    is_creator = project.created_by == user
    membership = ProjectMember.objects.filter(project=project, user=user).first()

    if not is_creator and not membership and user.role != 'admin':
        messages.error(request, "You are not authorized to view this project.")
        return redirect('dashboard')

    if is_creator:
        role = "owner"
    elif membership:
        role = membership.role_in_project
    elif user.role == 'admin':
        role = "admin"
    else:
        role = None

    is_admin_user = (user.role == 'admin')
    is_admin_user = (user.role == 'admin')

    # Common data for all roles
    members = ProjectMember.objects.filter(project=project).select_related('user')
    stats = {}

    context = {
        'project': project,
        'role': role,
        'is_creator': is_creator,
        'members': members,
    }

    # ── OWNER / ADMIN: full management view ──
    if role == 'owner' or is_admin_user:
        datasets = Dataset.objects.filter(project=project).order_by('-created_at')
        tasks = AnnotationTask.objects.filter(project=project).select_related('image', 'assigned_to').order_by('created_at')

        annotators = members.filter(role_in_project='annotator')
        existing_member_ids = members.values_list('user_id', flat=True)
        potential_users = User.objects.exclude(id__in=existing_member_ids).exclude(id=project.created_by.id)

        stats = {
            'total_datasets': datasets.count(),
            'total_tasks': tasks.count(),
            'unassigned': tasks.filter(status='unassigned').count(),
            'assigned': tasks.filter(status='assigned').count(),
            'in_progress': tasks.filter(status='in_progress').count(),
            'submitted': tasks.filter(status='submitted').count(),
            'approved': tasks.filter(status='approved').count(),
            'rejected': tasks.filter(status='rejected').count(),
        }
        
        # Build batch assignment table for admin
        batch_codes = (
            AnnotationTask.objects.filter(project=project)
            .exclude(batch__isnull=True)
            .exclude(batch='')
            .values_list('batch', flat=True)
            .distinct()
            .order_by('batch')
        )
        batch_assignments = []
        for code in batch_codes:
            btasks = AnnotationTask.objects.filter(project=project, batch=code).select_related('assigned_to')
            total = btasks.count()
            assigned_to = btasks.first().assigned_to if btasks.exists() else None
            annotated = Annotation.objects.filter(task__in=btasks).count()
            submitted = btasks.filter(status__in=['submitted', 'approved']).count()
            # Determine status label
            if submitted == total:
                b_status = 'submitted'
            elif annotated > 0:
                b_status = 'in_progress'
            else:
                b_status = 'assigned'
            batch_assignments.append({
                'code': code,
                'total': total,
                'assigned_to': assigned_to,
                'annotated': annotated,
                'submitted': submitted,
                'status': b_status,
            })

        context.update({
            'datasets': datasets,
            'tasks': tasks,
            'annotators': annotators,
            'potential_users': potential_users,
            'stats': stats,
            'batch_assignments': batch_assignments,
            'unassigned_count': tasks.filter(status='unassigned').count(),
        })

        

    # ── ANNOTATOR: show only their batches in this project ──
    elif role == 'annotator':
        annotator_batch_codes = (
            AnnotationTask.objects.filter(project=project, assigned_to=user)
            .exclude(batch__isnull=True)
            .values_list('batch', flat=True)
            .distinct()
            .order_by('batch')
        )
        my_project_batches = []
        for batch_code in annotator_batch_codes:
            batch_tasks = AnnotationTask.objects.filter(batch=batch_code, assigned_to=user).select_related('image')
            total = batch_tasks.count()
            annotated = Annotation.objects.filter(task__in=batch_tasks).count()
            all_annotated = annotated >= total
            is_fully_submitted = batch_tasks.filter(status__in=['submitted', 'approved']).count() == total
            first_task = (
                batch_tasks.filter(status='rejected').order_by('created_at').first()
                or batch_tasks.filter(status='assigned').order_by('created_at').first()
                or batch_tasks.filter(status='in_progress').order_by('created_at').first()
                or batch_tasks.order_by('created_at').first()
            )
            my_project_batches.append({
                'code': batch_code,
                'total': total,
                'annotated': annotated,
                'all_annotated': all_annotated,
                'is_fully_submitted': is_fully_submitted,
                'first_task': first_task,
            })

        def batch_priority(b):
            if b['is_fully_submitted']:
                return 3  # Last
            if b['all_annotated']:
                return 1  # First (Ready to Submit)
            return 2      # Middle (In Progress)

        # Sort the list in place
        my_project_batches.sort(key=batch_priority)

        tasks_qs = AnnotationTask.objects.filter(project=project, assigned_to=user)
        tasks_qs = AnnotationTask.objects.filter(project=project, assigned_to=user)
        stats = {
            'total_tasks': tasks_qs.count(),
            'assigned': tasks_qs.filter(status='assigned').count(),
            'in_progress': tasks_qs.filter(status='in_progress').count(),
            'submitted': tasks_qs.filter(status__in=['submitted', 'approved']).count(),
        }
        context.update({    
            'my_project_batches': my_project_batches,
            'stats': stats,
        })

    # ── REVIEWER: show submitted batches in this project ──
    elif role == 'reviewer':
        submitted_batch_codes = (
            AnnotationTask.objects.filter(project=project, status='submitted')
            .exclude(batch__isnull=True)
            .values_list('batch', flat=True)
            .distinct()
            .order_by('batch')
        )
        reviewer_project_batches = []
        for batch_code in submitted_batch_codes:
            batch_tasks = AnnotationTask.objects.filter(batch=batch_code).select_related('assigned_to')
            total = batch_tasks.count()
            submitted = batch_tasks.filter(status='submitted').count()
            approved = batch_tasks.filter(status='approved').count()
            rejected = batch_tasks.filter(status='rejected').count()
            annotated_by = batch_tasks.first().assigned_to if batch_tasks.exists() else None
            first_task = batch_tasks.filter(status='submitted').order_by('created_at').first()
            reviewer_project_batches.append({
                'code': batch_code,
                'total': total,
                'submitted': submitted,
                'approved': approved,
                'rejected': rejected,
                'annotated_by': annotated_by,
                'first_task': first_task,
            })

        context.update({
            'reviewer_project_batches': reviewer_project_batches,
        })

    return render(request, 'projects/detail.html', context)


# ─────────────────────────────────────────────────────────────
# ADD MEMBER
# ─────────────────────────────────────────────────────────────

@login_required
def add_member_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if project.created_by != request.user:
        messages.error(request, "Only the project owner can add members.")
        return redirect('project_detail', project_id=project.id)

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role_in_project = request.POST.get('role')

        if not user_id or not role_in_project:
            messages.error(request, "Invalid member data.")
            return redirect('project_detail', project_id=project.id)

        user_to_add = get_object_or_404(User, id=user_id)

        if ProjectMember.objects.filter(project=project, user=user_to_add).exists():
            messages.warning(request, f"{user_to_add.email} is already a member.")
        else:
            ProjectMember.objects.create(
                project=project, user=user_to_add, role_in_project=role_in_project
            )
            messages.success(
                request,
                f"Added {user_to_add.first_name} as {role_in_project} successfully!",
            )

    return redirect('project_detail', project_id=project.id)

    return redirect('project_detail', project_id=project.id)

# -------------------------------------------------------------
# DOWNLOAD ANNOTATIONS
# -------------------------------------------------------------

@login_required
def download_annotations_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    user = request.user
    is_owner = project.created_by == user
    is_admin = user.role == 'admin'

    if not is_owner and not is_admin:
        messages.error(request, 'You are not authorized to download annotations.')
        return redirect('dashboard')

    tasks = AnnotationTask.objects.filter(project=project)
    total_tasks = tasks.count()
    approved_tasks = tasks.filter(status='approved').count()

    if total_tasks == 0 or total_tasks != approved_tasks:
        messages.error(request, 'You can only download annotations when 100% of tasks are approved.')
        return redirect('project_detail', project_id=project.id)

    annotations = Annotation.objects.filter(task__project=project, status='approved').select_related('task__image')
    
    data = []
    for ann in annotations:
        data.append({
            'image_filename': ann.task.image.filename,
            'image_url': ann.task.image.storage_url,
            'labels': ann.labels,
            'batch': ann.task.batch
        })
        
    import json
    from django.http import HttpResponse
    response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename=annotations_{project.id}.json'
    return response

