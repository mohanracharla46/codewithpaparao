from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app import db
from app.middleware.auth import login_required
from app.models.models import Course, Module, Lesson, StudentProgress, Bookmark, Certificate, Profile
import uuid
from datetime import datetime

course_bp = Blueprint('course', __name__)

@course_bp.route('/')
def list_courses():
    search_query = request.args.get('search', '').strip()
    difficulty_filter = request.args.get('difficulty', '').strip()
    
    query = Course.query.filter(Course.deleted_at.is_(None), Course.is_published.is_(True))
    
    if search_query:
        query = query.filter(Course.title.ilike(f"%{search_query}%") | Course.description.ilike(f"%{search_query}%"))
        
    if difficulty_filter:
        query = query.filter(Course.difficulty == difficulty_filter)
        
    courses = query.order_by(Course.created_at.desc()).all()
    return render_template('courses/list.html', courses=courses, search=search_query, difficulty=difficulty_filter)

@course_bp.route('/<course_id>')
@login_required
def detail(course_id):
    course = Course.query.filter_by(id=course_id, deleted_at=None).first_or_404()
    
    # Calculate progress if student
    user_id = session['user_id']
    role = session['user_role']
    
    progress_pct = 0
    completed_lesson_ids = []
    
    total_lessons = sum(len(m.lessons) for m in course.modules)
    
    if role == 'student':
        # Get completed lessons in this course
        completed_progress = StudentProgress.query.filter(
            StudentProgress.student_id == user_id,
            StudentProgress.lesson_id.in_([l.id for m in course.modules for l in m.lessons])
        ).all()
        completed_lesson_ids = [p.lesson_id for p in completed_progress]
        
        if total_lessons > 0:
            progress_pct = int((len(completed_lesson_ids) / total_lessons) * 100)
            
    # Check if certificate is issued
    certificate = Certificate.query.filter_by(student_id=user_id, course_id=course_id).first()

    return render_template('courses/detail.html', 
                           course=course, 
                           progress_pct=progress_pct, 
                           completed_lesson_ids=completed_lesson_ids,
                           total_lessons=total_lessons,
                           certificate=certificate)

@course_bp.route('/lessons/<lesson_id>')
@login_required
def lesson_view(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    module = lesson.module
    course = module.course
    
    user_id = session['user_id']
    
    # Mark as completed automatically or update progress database records
    # To prevent issues, let's mark it as completed or allow the student to toggle it.
    # The requirement is "Track Progress" - we can mark it completed when they visit or hit a button.
    # Let's check if there's already a progress record
    progress = StudentProgress.query.filter_by(student_id=user_id, lesson_id=lesson_id).first()
    is_completed = progress is not None
    
    # Check bookmark state
    bookmark = Bookmark.query.filter_by(student_id=user_id, lesson_id=lesson_id).first()
    is_bookmarked = bookmark is not None
    
    # Get all lessons in this course for sidebar layout
    # Course -> Modules -> Lessons
    # Let's collect them in a flat/structured list
    sidebar_modules = course.modules # already sorted by sort_order
    
    # Find next and previous lessons
    flat_lessons = [l for m in sidebar_modules for l in m.lessons]
    current_idx = next((i for i, l in enumerate(flat_lessons) if l.id == lesson_id), -1)
    
    prev_lesson = flat_lessons[current_idx - 1] if current_idx > 0 else None
    next_lesson = flat_lessons[current_idx + 1] if current_idx < len(flat_lessons) - 1 else None

    # Load quiz for this module if it exists
    quiz = next((q for q in module.quizzes), None)

    return render_template('courses/lesson.html', 
                           lesson=lesson, 
                           module=module, 
                           course=course,
                           sidebar_modules=sidebar_modules,
                           is_completed=is_completed,
                           is_bookmarked=is_bookmarked,
                           prev_lesson=prev_lesson,
                           next_lesson=next_lesson,
                           quiz=quiz)

@course_bp.route('/lessons/<lesson_id>/complete', methods=['POST'])
@login_required
def complete_lesson(lesson_id):
    user_id = session['user_id']
    
    # Add progress record
    existing = StudentProgress.query.filter_by(student_id=user_id, lesson_id=lesson_id).first()
    if not existing:
        progress = StudentProgress(student_id=user_id, lesson_id=lesson_id)
        db.session.add(progress)
        db.session.commit()
        
    # Check if this triggers course completion and certificate issuance
    lesson = Lesson.query.get_or_404(lesson_id)
    course = lesson.module.course
    
    flat_lessons = [l for m in course.modules for l in m.lessons]
    total_lessons = len(flat_lessons)
    
    completed_count = StudentProgress.query.filter(
        StudentProgress.student_id == user_id,
        StudentProgress.lesson_id.in_([l.id for l in flat_lessons])
    ).count()
    
    certificate_generated = False
    cert_code = None
    
    if completed_count == total_lessons and total_lessons > 0:
        # Check if already issued
        existing_cert = Certificate.query.filter_by(student_id=user_id, course_id=course.id).first()
        if not existing_cert:
            cert_code = f"CERT-{course.title[:3].upper()}-{str(uuid.uuid4())[:8].upper()}"
            # Render a dummy static certificate or point to a placeholder generator
            cert = Certificate(
                student_id=user_id,
                course_id=course.id,
                certificate_code=cert_code,
                pdf_url=f"/courses/certificates/download/{cert_code}"
            )
            db.session.add(cert)
            db.session.commit()
            certificate_generated = True
            
            # Send notification
            from app.services.notification_service import NotificationService
            NotificationService.send_notification(
                user_id=user_id,
                title="Course Completed! 🎓",
                message=f"Congratulations! You have completed '{course.title}' and earned a certificate. Code: {cert_code}"
            )

    return jsonify({
        'status': 'success', 
        'completed': True,
        'progress_pct': int((completed_count / total_lessons) * 100) if total_lessons > 0 else 0,
        'certificate_generated': certificate_generated,
        'certificate_code': cert_code
    })

@course_bp.route('/lessons/<lesson_id>/bookmark', methods=['POST'])
@login_required
def toggle_bookmark(lesson_id):
    user_id = session['user_id']
    bookmark = Bookmark.query.filter_by(student_id=user_id, lesson_id=lesson_id).first()
    
    if bookmark:
        db.session.delete(bookmark)
        db.session.commit()
        bookmarked = False
    else:
        new_bookmark = Bookmark(student_id=user_id, lesson_id=lesson_id)
        db.session.add(new_bookmark)
        db.session.commit()
        bookmarked = True
        
    return jsonify({'status': 'success', 'bookmarked': bookmarked})

@course_bp.route('/certificates/download/<cert_code>')
@login_required
def download_certificate(cert_code):
    cert = Certificate.query.filter_by(certificate_code=cert_code).first_or_404()
    
    # Security check: Admins/super admins or the student themselves can access
    if session['user_role'] == 'student' and cert.student_id != session['user_id']:
        flash('Unauthorized certificate access.', 'danger')
        return redirect(url_for('dashboard.index'))
        
    return render_template('courses/certificate_pdf.html', cert=cert)

LANG_COURSES = {
    'c': {
        'title': 'C Programming',
        'difficulty': 'beginner',
        'description': 'Learn memory management, pointers, file handling, and structured coding patterns from the roots up.',
        'theme_color': '#0284c7',
        'theme_bg': 'rgba(2, 132, 199, 0.08)',
        'theme_light': '#e0f2fe',
        'icon_class': 'devicon-c-plain colored',
        'why_learn': 'C is the lingua franca of systems programming. Understanding C gives you a clear mental model of how computer memory works, how files are managed at the system level, and how to write extremely efficient code.',
        'code_snippet': """#include <stdio.h>

int main() {
    int x = 42;
    int *p = &x;
    
    printf("Value of x: %d\\n", x);
    printf("Memory address of x: %p\\n", (void*)&x);
    printf("Value stored in pointer p: %p\\n", (void*)p);
    printf("Value dereferenced from p: %d\\n", *p);
    
    return 0;
}""",
        'modules': [
            {'title': 'Module 1: Introduction to C & Syntax', 'lessons': ['History & Setup', 'Data Types & Variables', 'Operators & Input/Output']},
            {'title': 'Module 2: Control flow & Functions', 'lessons': ['Conditional Statements', 'Loops (for, while, do-while)', 'Declaring & Calling Functions']},
            {'title': 'Module 3: Pointers & Arrays', 'lessons': ['Single & Multi-dimensional Arrays', 'Understanding Pointers', 'Pointer Arithmetic']},
            {'title': 'Module 4: Memory Management', 'lessons': ['Dynamic Allocation (malloc, calloc)', 'Freeing Memory', 'File Handling in C']}
        ],
        'faqs': [
            {'q': 'Is this course suitable for complete beginners?', 'a': 'Yes, C is a fantastic first language because it explains what is happening under the hood.'},
            {'q': 'Do I need a specific operating system?', 'a': 'No, C can be written and compiled on Windows, macOS, or Linux. We cover compiler setup for all of them.'}
        ]
    },
    'cpp': {
        'title': 'C++ Development',
        'difficulty': 'intermediate',
        'description': 'Master Object-Oriented programming, templates, STL containers, and high-performance system logic.',
        'theme_color': '#6366f1',
        'theme_bg': 'rgba(99, 102, 241, 0.08)',
        'theme_light': '#e0e7ff',
        'icon_class': 'devicon-cplusplus-plain colored',
        'why_learn': 'C++ combines systems programming with high-level abstractions like Object-Oriented Programming (OOP) and Generic Programming. It is the language of choice for game engines, operating systems, and finance.',
        'code_snippet': """#include <iostream>
#include <vector>
#include <string>

class Developer {
public:
    std::string name;
    void code() {
        std::cout << name << " is writing C++!" << std::endl;
    }
};

int main() {
    Developer dev;
    dev.name = "Papa Rao";
    dev.code();
    return 0;
}""",
        'modules': [
            {'title': 'Module 1: C++ Basics & Setup', 'lessons': ['Setting up g++', 'Namespaces & Standard I/O', 'Reference Variables']},
            {'title': 'Module 2: Object-Oriented C++', 'lessons': ['Classes & Objects', 'Access Modifiers', 'Constructors & Destructors']},
            {'title': 'Module 3: Advanced OOP', 'lessons': ['Inheritance & Polymorphism', 'Virtual Functions', 'Encapsulation & Abstraction']},
            {'title': 'Module 4: Standard Template Library (STL)', 'lessons': ['Vectors & Lists', 'Maps & Sets', 'Algorithms & Iterators']}
        ],
        'faqs': [
            {'q': 'Should I learn C before learning C++?', 'a': 'While not strictly required, knowing C helps. However, we teach C++ starting from fundamentals so you can jump straight in.'},
            {'q': 'What kinds of projects will I build?', 'a': 'You will build a terminal-based RPG game and a high-performance memory manager simulator.'}
        ]
    },
    'java': {
        'title': 'Java Core',
        'difficulty': 'intermediate',
        'description': 'Build multi-threaded backend applications, interfaces, exception frameworks, and Java Virtual Machine concepts.',
        'theme_color': '#ea580c',
        'theme_bg': 'rgba(234, 88, 12, 0.08)',
        'theme_light': '#ffedd5',
        'icon_class': 'devicon-java-plain colored',
        'why_learn': 'Java is the backbone of enterprise web backends, Android applications, and financial transactions. Its "Write Once, Run Anywhere" philosophy and robust Garbage Collector make it incredibly popular.',
        'code_snippet': """import java.util.List;
import java.util.ArrayList;

public class Main {
    public static void main(String[] args) {
        List<String> tracks = new ArrayList<>();
        tracks.add("C");
        tracks.add("Python");
        tracks.add("Java");
        
        tracks.forEach(track -> System.out.println("Track: " + track));
    }
}""",
        'modules': [
            {'title': 'Module 1: Java Setup & JVM', 'lessons': ['JDK, JRE & JVM', 'Variables & Operators', 'Conditional Blocks']},
            {'title': 'Module 2: Object-Oriented Java', 'lessons': ['Classes, Objects & Packages', 'Inheritance & Interface', 'Abstract Classes']},
            {'title': 'Module 3: Exception Handling & Generics', 'lessons': ['Try-Catch-Finally Blocks', 'Custom Exceptions', 'Generic Classes & Methods']},
            {'title': 'Module 4: Concurrency & Multithreading', 'lessons': ['Creating Threads', 'Synchronization', 'Executor Service Framework']}
        ],
        'faqs': [
            {'q': 'Do we cover Spring Boot?', 'a': 'This course covers Java Standard Edition (SE) core concepts. It prepares you perfectly for Spring Boot frameworks.'},
            {'q': 'Is JVM memory architecture covered?', 'a': 'Yes, we dedicate sections to Heap vs. Stack memory allocation and Garbage Collection tuning.'}
        ]
    },
    'python': {
        'title': 'Python Core',
        'difficulty': 'beginner',
        'description': 'Learn scripting, control flows, data manipulation libraries, and Django/Flask full stack integration.',
        'theme_color': '#ca8a04',
        'theme_bg': 'rgba(202, 138, 4, 0.08)',
        'theme_light': '#fef9c3',
        'icon_class': 'devicon-python-plain colored',
        'why_learn': 'Python is the world\'s most popular language for beginners, data scientists, AI engineers, and automation scripts. Its elegant syntax allows you to focus on solving problems rather than boilerplate code.',
        'code_snippet': """def greet(name: str) -> str:
    return f"Hello, {name}!"

# Dynamic list comprehension
squares = [x**2 for x in range(10) if x % 2 == 0]

print(greet("Papa Rao"))
print("Even squares:", squares)""",
        'modules': [
            {'title': 'Module 1: Python Introduction', 'lessons': ['Setup & Python Interpreter', 'Variables & Basic Data Types', 'Control Structures (if, for, while)']},
            {'title': 'Module 2: Data Structures & Functions', 'lessons': ['Lists, Tuples, Dictionaries', 'Defining Functions', 'Args & Kwargs']},
            {'title': 'Module 3: OOP in Python', 'lessons': ['Classes & Magic Methods', 'Inheritance & Properties', 'Modules & Imports']},
            {'title': 'Module 4: Standard Library & File I/O', 'lessons': ['Reading/Writing Files', 'Regular Expressions', 'Context Managers (with statement)']}
        ],
        'faqs': [
            {'q': 'Will this help me get into Data Science?', 'a': 'Absolutely! Python Core is the absolute prerequisite for Pandas, NumPy, and Machine Learning.'},
            {'q': 'Do we build web apps?', 'a': 'Yes, the final capstone project builds a simple Flask application.'}
        ]
    },
    'dsa': {
        'title': 'DSA Masterclass',
        'difficulty': 'advanced',
        'description': 'Optimize runtime complexity with trees, graphs, sorting algorithms, dynamic programming, and logic.',
        'theme_color': '#10b981',
        'theme_bg': 'rgba(16, 185, 129, 0.08)',
        'theme_light': '#d1fae5',
        'icon_class': 'fa-solid fa-project-diagram',
        'why_learn': 'Data Structures & Algorithms (DSA) are the foundation of problem-solving in computer science. They are also the core topics tested during technical interviews at leading tech companies like Google, Meta, and Microsoft.',
        'code_snippet': """# Binary Search Implementation
def binary_search(arr, target):
    low, high = 0, len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1""",
        'modules': [
            {'title': 'Module 1: Complexity & Basic Structures', 'lessons': ['Asymptotic Analysis (Big O)', 'Arrays & Linked Lists', 'Stacks & Queues']},
            {'title': 'Module 2: Trees & Graphs', 'lessons': ['Binary Trees & BSTs', 'DFS & BFS Traversals', 'Graph Adjacency Lists']},
            {'title': 'Module 3: Sorting & Searching', 'lessons': ['Merge Sort & Quick Sort', 'Binary Search & Hash Tables', 'Two Pointers & Slidewindow']},
            {'title': 'Module 4: Advanced Algorithms', 'lessons': ['Greedy Approach', 'Recursion & Backtracking', 'Dynamic Programming Basics']}
        ],
        'faqs': [
            {'q': 'Which language is used in the course?', 'a': 'Algorithms are explained conceptually, with code implementations provided in Python, Java, and C++.'},
            {'q': 'Does this course prepare me for LeetCode?', 'a': 'Yes, the curriculum is designed to teach you the patterns needed to solve medium-to-hard LeetCode questions.'}
        ]
    }
}

def get_db_courses_for_lang(lang_key):
    import re
    lang_key = lang_key.lower().strip()
    all_published_courses = Course.query.filter(Course.deleted_at.is_(None), Course.is_published.is_(True)).all()
    
    matching_courses = []
    for course in all_published_courses:
        title_lower = course.title.lower()
        
        is_match = False
        if lang_key == 'c':
            if re.search(r'\bc\b', title_lower) and not ('c++' in title_lower or 'c#' in title_lower):
                is_match = True
        elif lang_key == 'cpp':
            if 'c++' in title_lower or 'cpp' in title_lower:
                is_match = True
        elif lang_key == 'java':
            if 'java' in title_lower and 'javascript' not in title_lower:
                is_match = True
        elif lang_key == 'python':
            if 'python' in title_lower:
                is_match = True
        elif lang_key == 'dsa':
            if 'dsa' in title_lower or 'data structure' in title_lower or 'algorithm' in title_lower:
                is_match = True
                
        if is_match:
            matching_courses.append(course)
            
    return matching_courses

@course_bp.route('/lang/<lang_key>')
def language_detail(lang_key):
    lang_key = lang_key.lower().strip()
    if lang_key not in LANG_COURSES:
        return redirect(url_for('course.list_courses'))
        
    lang_data = LANG_COURSES[lang_key]
    
    # Query all matching published courses in database
    db_courses = get_db_courses_for_lang(lang_key)
    
    # If no courses exist for this language, and user is logged in, auto-seed the default one
    if not db_courses and session.get('user_id'):
        try:
            # Find any admin profile to assign as creator
            admin = Profile.query.filter_by(role='admin').first() or Profile.query.filter_by(role='super_admin').first()
            admin_id = admin.id if admin else session['user_id']
            
            course = Course(
                title=lang_data['title'],
                description=lang_data['description'],
                difficulty=lang_data['difficulty'],
                is_published=True,
                created_by=admin_id
            )
            db.session.add(course)
            db.session.commit()
            
            # Create modules & lessons dynamically
            for i, mod_data in enumerate(lang_data['modules']):
                module = Module(
                    course_id=course.id,
                    title=mod_data['title'],
                    sort_order=i
                )
                db.session.add(module)
                db.session.commit()
                
                for j, les_title in enumerate(mod_data['lessons']):
                    lesson = Lesson(
                        module_id=module.id,
                        title=les_title,
                        content_type='text',
                        text_content=f"Welcome to the {les_title} lesson. In this lesson of {course.title}, we explore fundamental principles and build hands-on applications.",
                        sort_order=j
                    )
                    db.session.add(lesson)
            db.session.commit()
            
            # Re-fetch matching courses to include the newly created one
            db_courses = get_db_courses_for_lang(lang_key)
        except Exception:
            db.session.rollback()
            
    # Link the Hero card button to the first matching course if it exists
    course_id = db_courses[0].id if db_courses else None
            
    return render_template('courses/language_detail.html', 
                           lang=lang_key, 
                           data=lang_data, 
                           db_courses=db_courses,
                           course_id=course_id)
