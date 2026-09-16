from datetime import datetime

from sqlalchemy import Boolean, Column, Integer, String, Text, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="student")
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", uselist=False, back_populates="user")
    company = relationship("Company", uselist=False, back_populates="user")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    college = Column(String(255), nullable=True)
    degree = Column(String(255), nullable=True)
    branch = Column(String(255), nullable=True)
    skills = Column(Text, nullable=True)
    technologies = Column(Text, nullable=True)
    experience_level = Column(String(100), default="Beginner")
    bio = Column(Text, nullable=True)
    github = Column(String(255), nullable=True)
    linkedin = Column(String(255), nullable=True)
    portfolio = Column(String(255), nullable=True)
    profile_photo = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="student")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    company_name = Column(String(255), nullable=False)
    industry = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    logo = Column(String(255), nullable=True)
    company_size = Column(String(100), nullable=True)
    technologies = Column(Text, nullable=True)

    user = relationship("User", back_populates="company")
    problems = relationship("Problem", back_populates="company")


class Problem(Base):
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False)
    required_skills = Column(Text, nullable=True)
    technologies = Column(Text, nullable=True)
    difficulty = Column(String(50), default="Beginner")
    duration = Column(String(100), nullable=True)
    deadline = Column(String(50), nullable=True)
    payment_status = Column(String(50), default="Unpaid")
    payment_amount = Column(Float, default=0)
    number_of_students = Column(Integer, default=1)
    requirements = Column(Text, nullable=True)
    deliverables = Column(Text, nullable=True)
    attachments = Column(Text, nullable=True)
    github_repository = Column(String(255), nullable=True)
    instructions = Column(Text, nullable=True)
    remote_option = Column(String(50), default="Remote")
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="problems")
    applications = relationship("Application", back_populates="problem")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    introduction = Column(Text, nullable=True)
    suitability = Column(Text, nullable=True)
    relevant_skills = Column(Text, nullable=True)
    previous_projects = Column(Text, nullable=True)
    github_link = Column(String(255), nullable=True)
    portfolio_link = Column(String(255), nullable=True)
    estimated_completion_time = Column(String(100), nullable=True)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    problem = relationship("Problem", back_populates="applications")


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    status = Column(String(50), default="ASSIGNED")
    created_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, nullable=False)
    receiver_id = Column(Integer, nullable=False)
    assignment_id = Column(Integer, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    message = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    reviewer_id = Column(Integer, nullable=False)
    reviewed_user_id = Column(Integer, nullable=False)
    rating = Column(Float, default=0)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    github_repository = Column(String(255), nullable=True)
    live_demo = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    screenshots = Column(Text, nullable=True)
    testing_info = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)
    status = Column(String(50), default="submitted")
    created_at = Column(DateTime, default=datetime.utcnow)
