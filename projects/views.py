from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django import forms
from django.db.models import Count, Q
from .models import Project, ProjectMember
from accounts.models import User
from datasets.models import Dataset
from annotations.models import AnnotationTask, Annotation

# Custom Form for Project Creation
class ProjectForm(forms.ModelForm):
    labels_raw = forms.CharField(
        max_length=1000, 
        widget=forms.TextInput(attrs={'placeholder': 'car, person, traffic light, dog'}),
        help_text="Enter labels separated by commas"
    )

    class Meta:
        model = Project
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe the goal of this annotation project...'}),
        }

@login_required
def dashboard_view(request):
    user = request.user
    
    # 1. Projects created by this user
    created_projects = Project.objects.filter(created_by=user).order_by('-created_at')
    
    # 2. Projects this user is a member of
    member_projects = Project.objects.filter(projectmember__user=user).order_by('-created_at')
    
    # 3. Tasks assigned to this user (Annotator perspective) — paginated 25/page
    all_assigned_tasks = AnnotationTask.objects.filter(
        assigned_to=user
    ).exclude(status='approved').select_related('project', 'image').order_by('-created_at')
    
    paginator = Paginator(all_assigned_tasks, 25)
    page_number = request.GET.get('task_page', 1)
    assigned_tasks_page = paginator.get_page(page_number)
    
    # 4. Tasks pending review (Reviewer perspective)
    reviewer_project_ids = ProjectMember.objects.filter(
        user=user, 
        role_in_project='reviewer'
    ).values_list('project_id', flat=True)
    
    pending_reviews = AnnotationTask.objects.filter(
        project_id__in=reviewer_project_ids,
        status='submitted'
    ).select_related('project', 'image', 'assigned_to').order_by('-created_at')

    context = {
        'created_projects': created_projects,
        'created_projects_count': created_projects.count(),
        'member_projects': member_projects,
        'member_projects_count': member_projects.count(),
        'assigned_tasks': assigned_tasks_page,
        'assigned_tasks_total': all_assigned_tasks.count(),
        'pending_reviews': pending_reviews,
        'pending_reviews_count': pending_reviews.count(),
    }
    return render(request, 'dashboard.html', context)

@login_required
def admin_dashboard_view(request):
    """Admin-only dashboard with sidenav, project management, profile and review stats."""
    if request.user.role != 'admin':
        messages.error(request, "Admin access required.")
        return redirect('dashboard')
    
    # All projects
    all_projects = Project.objects.all().select_related('created_by').order_by('-created_at')
    
    # Per-annotator stats: how many annotations each annotator has done
    annotator_stats = (
        Annotation.objects
        .values('annotated_by__id', 'annotated_by__first_name', 'annotated_by__last_name', 'annotated_by__email')
        .annotate(
            total_annotations=Count('id'),
            approved_annotations=Count('id', filter=Q(status='approved')),
            submitted_annotations=Count('id', filter=Q(status='submitted')),
            rejected_annotations=Count('id', filter=Q(status='rejected')),
        )
        .order_by('-total_annotations')
    )
    
    # Per-project review stats
    project_review_stats = []
    for project in all_projects:
        tasks = AnnotationTask.objects.filter(project=project)
        total = tasks.count()
        approved = tasks.filter(status='approved').count()
        submitted = tasks.filter(status='submitted').count()
        in_progress = tasks.filter(status='in_progress').count()
        unassigned = tasks.filter(status='unassigned').count()
        rejected = tasks.filter(status='rejected').count()
        
        # Per-annotator breakdown for this project
        annotators_in_project = ProjectMember.objects.filter(
            project=project, role_in_project='annotator'
        ).select_related('user')
        
        annotator_breakdown = []
        for member in annotators_in_project:
            done = Annotation.objects.filter(
                task__project=project,
                annotated_by=member.user
            ).count()
            annotator_breakdown.append({
                'user': member.user,
                'annotations_done': done,
            })
        
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
    
    # All registered non-admin users
    all_users = User.objects.all().order_by('first_name', 'last_name')
    
    context = {
        'all_projects': all_projects,
        'all_projects_count': all_projects.count(),
        'project_review_stats': project_review_stats,
        'annotator_stats': annotator_stats,
        'all_users': all_users,
        'all_users_count': all_users.count(),
        'active_tab': request.GET.get('tab', 'projects'),
    }
    return render(request, 'admin_dashboard.html', context)

@login_required
def project_create_view(request):
    if request.user.role != "admin":
        return redirect("no_access")
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            
            # Process label set
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

@login_required
def project_detail_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    user = request.user
    
    # Check if user is creator or member
    is_creator = (project.created_by == user)
    membership = ProjectMember.objects.filter(project=project, user=user).first()
    
    if not is_creator and not membership:
        messages.error(request, "You are not authorized to view this project.")
        return redirect('dashboard')
        
    role = "owner" if is_creator else membership.role_in_project
    
    # Fetch datasets for this project
    datasets = Dataset.objects.filter(project=project).order_by('-created_at')
    
    # Fetch members of this project
    members = ProjectMember.objects.filter(project=project).select_related('user')
    
    # Fetch tasks
    tasks = AnnotationTask.objects.filter(project=project).select_related('image', 'assigned_to').order_by('-created_at')
    
    # Get lists of possible annotators to assign tasks to
    annotators = members.filter(role_in_project='annotator')
    
    # All users not already in the project (for adding members)
    existing_member_ids = members.values_list('user_id', flat=True)
    potential_users = User.objects.exclude(id__in=existing_member_ids).exclude(id=project.created_by.id)
    
    # Calculate stats for dashboard
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
    
    context = {
        'project': project,
        'role': role,
        'is_creator': is_creator,
        'datasets': datasets,
        'members': members,
        'tasks': tasks,
        'annotators': annotators,
        'potential_users': potential_users,
        'stats': stats,
    }
    return render(request, 'projects/detail.html', context)

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
        
        # Check if already a member
        if ProjectMember.objects.filter(project=project, user=user_to_add).exists():
            messages.warning(request, f"{user_to_add.email} is already a member.")
        else:
            ProjectMember.objects.create(
                project=project,
                user=user_to_add,
                role_in_project=role_in_project
            )
            messages.success(request, f"Added {user_to_add.first_name} as {role_in_project} successfully!")
            
    return redirect('project_detail', project_id=project.id)
