from typing import Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = 'student'


class StudentCreate(BaseModel):
    name: str
    college: Optional[str] = None
    degree: Optional[str] = None
    branch: Optional[str] = None
    skills: Optional[str] = None


class CompanyCreate(BaseModel):
    company_name: str
    industry: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None


class ProblemCreate(BaseModel):
    title: str
    description: str
    category: str
    required_skills: Optional[str] = None
    technologies: Optional[str] = None
    difficulty: str = 'Beginner'
    duration: Optional[str] = None
    deadline: Optional[str] = None
    payment_status: str = 'Unpaid'
    payment_amount: Optional[float] = 0
    number_of_students: int = 1
    requirements: Optional[str] = None
    deliverables: Optional[str] = None
    attachments: Optional[str] = None
    github_repository: Optional[str] = None
    instructions: Optional[str] = None
    remote_option: str = 'Remote'
