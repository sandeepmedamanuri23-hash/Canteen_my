from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.auth import hash_password, authenticate_user
from app.database import Base, engine, get_db
from app.models import User, Student, Company, Problem, Application, Assignment, Message, Notification, Submission

app = FastAPI(title='Reverse Internship', version='1.0.0')
app.mount('/static', StaticFiles(directory='app/static'), name='static')

template_env = Environment(
    loader=FileSystemLoader('app/templates'),
    autoescape=select_autoescape(['html', 'xml']),
)

Base.metadata.create_all(bind=engine)


def render_template(request: Request, template_name: str, **context):
    template = template_env.get_template(template_name)
    html = template.render(
        request=request,
        url_for=lambda endpoint, **params: request.url_for(endpoint, **params),
        **context,
    )
    return HTMLResponse(html)


def get_session_user(db: Session, request: Request):
    user_id = request.cookies.get('user_id')
    if not user_id:
        return None
    return db.query(User).filter(User.id == int(user_id)).first()


def get_user_role(user: Optional[User]) -> str:
    if not user:
        return 'guest'
    return user.role


@app.get('/', response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    problems = db.query(Problem).order_by(Problem.created_at.desc()).limit(3).all()
    return render_template(request, 'index.html', problems=problems)


@app.get('/login', response_class=HTMLResponse)
async def login_page(request: Request):
    return render_template(request, 'login.html')


@app.post('/login')
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, email, password)
    if not user:
        raise HTTPException(status_code=401, detail='Invalid credentials')

    redirect_url = '/student/dashboard' if user.role == 'student' else '/company/dashboard'
    if user.role == 'admin':
        redirect_url = '/admin/dashboard'

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key='user_id', value=str(user.id), httponly=True, samesite='lax')
    return response


@app.get('/register', response_class=HTMLResponse)
async def register_page(request: Request):
    return render_template(request, 'register.html')


@app.post('/register')
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form('student'),
    name: Optional[str] = Form(None),
    college: Optional[str] = Form(None),
    degree: Optional[str] = Form(None),
    branch: Optional[str] = Form(None),
    skills: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    industry: Optional[str] = Form(None),
    website: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail='Email already registered')

    new_user = User(email=email, password_hash=hash_password(password), role=role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if role == 'student':
        student = Student(
            user_id=new_user.id,
            name=name or 'Student',
            college=college,
            degree=degree,
            branch=branch,
            skills=skills,
        )
        db.add(student)
    elif role == 'company':
        company = Company(
            user_id=new_user.id,
            company_name=company_name or 'Company',
            industry=industry,
            website=website,
            description=description,
        )
        db.add(company)

    db.commit()

    redirect_url = '/student/dashboard' if role == 'student' else '/company/dashboard'
    if role == 'admin':
        redirect_url = '/admin/dashboard'

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key='user_id', value=str(new_user.id), httponly=True, samesite='lax')
    return response


@app.get('/student/dashboard', response_class=HTMLResponse)
async def student_dashboard(request: Request, db: Session = Depends(get_db)):
    current_user = get_session_user(db, request)
    if not current_user or current_user.role != 'student':
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    problems = db.query(Problem).order_by(Problem.created_at.desc()).limit(3).all()
    applications = db.query(Application).filter(Application.student_id == student.id).all() if student else []
    return render_template(request, 'student_dashboard.html', student=student, problems=problems, applications=applications, stats={
        'problems_solved': 12,
        'active_projects': 3,
        'applications': len(applications),
        'completed_projects': 8,
        'average_rating': 4.8,
    })


@app.get('/company/dashboard', response_class=HTMLResponse)
async def company_dashboard(request: Request, db: Session = Depends(get_db)):
    current_user = get_session_user(db, request)
    if not current_user or current_user.role != 'company':
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    company = db.query(Company).filter(Company.user_id == current_user.id).first()
    problems = db.query(Problem).filter(Problem.company_id == company.id).all() if company else []
    return render_template(request, 'company_dashboard.html', company=company, problems=problems, stats={
        'problems_posted': len(problems),
        'applications': 8,
        'active_assignments': 2,
        'completed_problems': 3,
    })


@app.get('/admin/dashboard', response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    current_user = get_session_user(db, request)
    if not current_user or current_user.role != 'admin':
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    total_students = db.query(Student).count()
    total_companies = db.query(Company).count()
    total_problems = db.query(Problem).count()
    active_assignments = db.query(Assignment).filter(Assignment.status != 'COMPLETED').count()
    completed_problems = db.query(Assignment).filter(Assignment.status == 'COMPLETED').count()
    applications = db.query(Application).count()
    return render_template(request, 'admin_dashboard.html', stats={
        'students': total_students,
        'companies': total_companies,
        'problems': total_problems,
        'active_assignments': active_assignments,
        'completed_problems': completed_problems,
        'applications': applications,
        'successes': 36,
    })


@app.get('/students', response_class=HTMLResponse)
async def students_list(request: Request, db: Session = Depends(get_db)):
    students = db.query(Student).all()
    return render_template(request, 'students.html', students=students)


@app.get('/companies', response_class=HTMLResponse)
async def companies_list(request: Request, db: Session = Depends(get_db)):
    companies = db.query(Company).all()
    return render_template(request, 'companies.html', companies=companies)


@app.get('/problems', response_class=HTMLResponse)
async def problems_marketplace(request: Request, db: Session = Depends(get_db)):
    problems = db.query(Problem).order_by(Problem.created_at.desc()).all()
    companies = {c.id: c for c in db.query(Company).all()}
    return render_template(request, 'problems.html', problems=problems, companies=companies)


@app.get('/problems/create', response_class=HTMLResponse)
async def create_problem_page(request: Request):
    return render_template(request, 'post_problem.html')


@app.post('/problems/create')
async def create_problem(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    required_skills: str = Form(...),
    technologies: str = Form(...),
    difficulty: str = Form(...),
    duration: str = Form(...),
    deadline: str = Form(...),
    payment_status: str = Form(...),
    payment_amount: float = Form(0),
    number_of_students: int = Form(1),
    requirements: str = Form(...),
    deliverables: str = Form(...),
    github_repository: str = Form(''),
    instructions: str = Form(''),
    remote_option: str = Form('Remote'),
    db: Session = Depends(get_db),
):
    current_user = get_session_user(db, request)
    if not current_user or current_user.role != 'company':
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    company = db.query(Company).filter(Company.user_id == current_user.id).first()
    if not company:
        raise HTTPException(status_code=404, detail='Company profile not found')

    problem = Problem(
        company_id=company.id,
        title=title,
        description=description,
        category=category,
        required_skills=required_skills,
        technologies=technologies,
        difficulty=difficulty,
        duration=duration,
        deadline=deadline,
        payment_status=payment_status,
        payment_amount=payment_amount,
        number_of_students=number_of_students,
        requirements=requirements,
        deliverables=deliverables,
        github_repository=github_repository,
        instructions=instructions,
        remote_option=remote_option,
    )
    db.add(problem)
    db.commit()
    return RedirectResponse(url='/company/dashboard', status_code=status.HTTP_303_SEE_OTHER)


@app.get('/problems/{problem_id}', response_class=HTMLResponse)
async def problem_detail(problem_id: int, request: Request, db: Session = Depends(get_db)):
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail='Problem not found')
    company = db.query(Company).filter(Company.id == problem.company_id).first()
    return render_template(request, 'problem_detail.html', problem=problem, company=company)


@app.post('/apply/{problem_id}')
async def apply_to_problem(
    problem_id: int,
    request: Request,
    introduction: str = Form(...),
    suitability: str = Form(...),
    relevant_skills: str = Form(...),
    previous_projects: str = Form(''),
    github_link: str = Form(''),
    portfolio_link: str = Form(''),
    estimated_completion_time: str = Form(''),
    db: Session = Depends(get_db),
):
    current_user = get_session_user(db, request)
    if not current_user or current_user.role != 'student':
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=404, detail='Student profile not found')

    application = Application(
        problem_id=problem_id,
        student_id=student.id,
        introduction=introduction,
        suitability=suitability,
        relevant_skills=relevant_skills,
        previous_projects=previous_projects,
        github_link=github_link,
        portfolio_link=portfolio_link,
        estimated_completion_time=estimated_completion_time,
    )
    db.add(application)
    db.commit()
    return RedirectResponse(url='/student/dashboard', status_code=status.HTTP_303_SEE_OTHER)


@app.post('/applications/{application_id}/accept')
async def accept_application(application_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_session_user(db, request)
    if not current_user or current_user.role != 'company':
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail='Application not found')

    application.status = 'accepted'
    company = db.query(Company).filter(Company.user_id == current_user.id).first()
    problem = db.query(Problem).filter(Problem.id == application.problem_id).first()
    student = db.query(Student).filter(Student.id == application.student_id).first()
    if company and problem and student:
        assignment = Assignment(
            problem_id=problem.id,
            student_id=student.id,
            company_id=company.id,
            status='ASSIGNED',
        )
        db.add(assignment)
    db.commit()
    return RedirectResponse(url='/company/dashboard', status_code=status.HTTP_303_SEE_OTHER)


@app.get('/student/profile', response_class=HTMLResponse)
async def student_profile(request: Request, db: Session = Depends(get_db)):
    current_user = get_session_user(db, request)
    if not current_user or current_user.role != 'student':
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    return render_template(request, 'student_profile.html', student=student, user=current_user)


@app.post('/student/profile/edit')
async def edit_student_profile(
    request: Request,
    name: str = Form(...),
    college: str = Form(''),
    degree: str = Form(''),
    branch: str = Form(''),
    skills: str = Form(''),
    technologies: str = Form(''),
    experience_level: str = Form('Beginner'),
    bio: str = Form(''),
    github: str = Form(''),
    linkedin: str = Form(''),
    portfolio: str = Form(''),
    db: Session = Depends(get_db),
):
    current_user = get_session_user(db, request)
    if not current_user or current_user.role != 'student':
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        student = Student(user_id=current_user.id, name=name)
        db.add(student)
    student.name = name
    student.college = college
    student.degree = degree
    student.branch = branch
    student.skills = skills
    student.technologies = technologies
    student.experience_level = experience_level
    student.bio = bio
    student.github = github
    student.linkedin = linkedin
    student.portfolio = portfolio
    db.commit()
    return RedirectResponse(url='/student/profile', status_code=status.HTTP_303_SEE_OTHER)


@app.get('/company/profile', response_class=HTMLResponse)
async def company_profile(request: Request, db: Session = Depends(get_db)):
    current_user = get_session_user(db, request)
    if not current_user or current_user.role != 'company':
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    company = db.query(Company).filter(Company.user_id == current_user.id).first()
    return render_template(request, 'company_profile.html', company=company, user=current_user)


@app.post('/company/profile/edit')
async def edit_company_profile(
    request: Request,
    company_name: str = Form(...),
    industry: str = Form(''),
    website: str = Form(''),
    description: str = Form(''),
    location: str = Form(''),
    technologies: str = Form(''),
    company_size: str = Form(''),
    db: Session = Depends(get_db),
):
    current_user = get_session_user(db, request)
    if not current_user or current_user.role != 'company':
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    company = db.query(Company).filter(Company.user_id == current_user.id).first()
    if not company:
        company = Company(user_id=current_user.id, company_name=company_name)
        db.add(company)
    company.company_name = company_name
    company.industry = industry
    company.website = website
    company.description = description
    company.location = location
    company.technologies = technologies
    company.company_size = company_size
    db.commit()
    return RedirectResponse(url='/company/profile', status_code=status.HTTP_303_SEE_OTHER)


@app.get('/student/portfolio/{student_id}', response_class=HTMLResponse)
async def student_portfolio(student_id: int, request: Request, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail='Student not found')
    return render_template(request, 'student_portfolio.html', student=student)


@app.get('/assignments', response_class=HTMLResponse)
async def assignments_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_session_user(db, request)
    if not current_user:
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    company = db.query(Company).filter(Company.user_id == current_user.id).first()
    if student:
        assignments = db.query(Assignment).filter(Assignment.student_id == student.id).all()
    elif company:
        assignments = db.query(Assignment).filter(Assignment.company_id == company.id).all()
    else:
        assignments = []
    return render_template(request, 'assignments.html', assignments=assignments)


@app.get('/messages', response_class=HTMLResponse)
async def messages_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_session_user(db, request)
    if not current_user:
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    messages = db.query(Message).filter((Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)).order_by(Message.created_at.desc()).all()
    return render_template(request, 'messages.html', messages=messages)


@app.post('/messages/send')
async def send_message(
    request: Request,
    receiver_id: int = Form(...),
    content: str = Form(...),
    assignment_id: int = Form(0),
    db: Session = Depends(get_db),
):
    current_user = get_session_user(db, request)
    if not current_user:
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        assignment_id=assignment_id if assignment_id else None,
        content=content,
        is_read=False,
    )
    db.add(message)
    db.commit()
    return RedirectResponse(url='/messages', status_code=status.HTTP_303_SEE_OTHER)


@app.get('/notifications', response_class=HTMLResponse)
async def notifications_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_session_user(db, request)
    if not current_user:
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    notifications = db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template(request, 'notifications.html', notifications=notifications)


@app.post('/submit/{assignment_id}')
async def submit_assignment(
    assignment_id: int,
    request: Request,
    github_repository: str = Form(''),
    live_demo: str = Form(''),
    description: str = Form(''),
    testing_info: str = Form(''),
    comments: str = Form(''),
    db: Session = Depends(get_db),
):
    current_user = get_session_user(db, request)
    if not current_user:
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail='Assignment not found')

    submission = Submission(
        assignment_id=assignment.id,
        github_repository=github_repository,
        live_demo=live_demo,
        description=description,
        testing_info=testing_info,
        comments=comments,
        status='submitted',
    )
    db.add(submission)
    assignment.status = 'SUBMITTED'
    db.commit()
    return RedirectResponse(url='/assignments', status_code=status.HTTP_303_SEE_OTHER)


@app.get('/logout')
async def logout():
    response = RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie('user_id')
    return response


@app.get('/health')
async def health_check():
    return {'status': 'ok'}
