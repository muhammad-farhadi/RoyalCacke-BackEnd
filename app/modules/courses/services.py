# app/modules/courses/services.py
from sqlalchemy.orm import Session
from . import models, schemas


# --- سرویس‌های دوره ---
def get_courses(db: Session, category: str = None, only_published: bool = True, skip: int = 0, limit: int = 10):
    query = db.query(models.Course)
    if only_published:
        query = query.filter(models.Course.is_published == True)
    if category:
        query = query.filter(models.Course.category == category)
    return query.order_by(models.Course.created_at.desc()).offset(skip).limit(limit).all()


def get_course_by_id(db: Session, course_id: int):
    return db.query(models.Course).filter(models.Course.id == course_id).first()


def create_course(db: Session, course: schemas.CourseCreate, image_url: str = None):
    db_course = models.Course(**course.model_dump(), image_url=image_url)
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course


def delete_course(db: Session, course_id: int):
    db_course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if db_course:
        db.delete(db_course)
        db.commit()
        return True
    return False


# --- سرویس‌های ویدیو (Lesson) ---
def create_lesson(db: Session, lesson: schemas.LessonCreate, video_url: str):
    db_lesson = models.Lesson(**lesson.model_dump(), video_url=video_url)
    db.add(db_lesson)

    # به‌روزرسانی خودکار تعداد جلسات دوره
    course = db.query(models.Course).filter(models.Course.id == lesson.course_id).first()
    if course:
        course.session_count += 1

    db.commit()
    db.refresh(db_lesson)
    return db_lesson


def delete_lesson(db: Session, lesson_id: int):
    db_lesson = db.query(models.Lesson).filter(models.Lesson.id == lesson_id).first()
    if db_lesson:
        course = db.query(models.Course).filter(models.Course.id == db_lesson.course_id).first()
        if course and course.session_count > 0:
            course.session_count -= 1

        db.delete(db_lesson)
        db.commit()
        return True
    return False
