import sys
import sqlite3
import hashlib
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox,
    QStackedWidget, QListWidget, QListWidgetItem, QLineEdit, QFormLayout, QDialog, QComboBox,
    QTextEdit, QGridLayout, QRadioButton, QButtonGroup, QSpinBox, QScrollArea
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

# Database Setup
def initialize_database():
    conn = sqlite3.connect('gestura.db')
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        FOREIGN KEY (teacher_id) REFERENCES users (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        options TEXT NOT NULL,
        correct_answer INTEGER NOT NULL,
        FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        quiz_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        total_questions INTEGER NOT NULL,
        FOREIGN KEY (student_id) REFERENCES users (id),
        FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
    )
    ''')

    conn.commit()
    return conn

def get_db_connection():
    return sqlite3.connect('gestura.db')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.resize(300, 200)
        layout = QVBoxLayout()

        form_layout = QFormLayout()
        
        self.username_input = QLineEdit(self)
        form_layout.addRow("Username:", self.username_input)

        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Password:", self.password_input)

        self.role_combobox = QComboBox(self)
        self.role_combobox.addItem("Student")
        self.role_combobox.addItem("Teacher")
        form_layout.addRow("Role:", self.role_combobox)
        
        layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        
        self.login_button = QPushButton("Login", self)
        self.login_button.clicked.connect(self.login)
        buttons_layout.addWidget(self.login_button)

        self.register_button = QPushButton("Register", self)
        self.register_button.clicked.connect(self.register)
        buttons_layout.addWidget(self.register_button)
        
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def login(self):
        username = self.username_input.text()
        password = hash_password(self.password_input.text())
        role = self.role_combobox.currentText().lower()

        if not username or not password:
            QMessageBox.warning(self, "Login Failed", "Please enter both username and password")
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ? AND password = ? AND role = ?", 
                       (username, password, role))
        user = cursor.fetchone()
        conn.close()

        if user:
            self.parent().user_id = user[0]
            self.parent().user_role = role
            self.parent().username = username
            self.accept()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username, password, or role")

    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()
        role = self.role_combobox.currentText().lower()

        if not username or not password:
            QMessageBox.warning(self, "Registration Failed", "Username and password are required")
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           (username, hash_password(password), role))
            conn.commit()
            QMessageBox.information(self, "Registration Successful", "You can now log in with your credentials")
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Registration Failed", "Username already exists")
        finally:
            conn.close()

class CreateQuizDialog(QDialog):
    def __init__(self, teacher_id, parent=None):
        super().__init__(parent)
        self.teacher_id = teacher_id
        self.questions = []
        
        self.setWindowTitle("Create Quiz")
        self.resize(600, 400)
        
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        self.quiz_title = QLineEdit()
        form_layout.addRow("Quiz Title:", self.quiz_title)
        layout.addLayout(form_layout)
        
        # Question count selection
        self.question_count_layout = QHBoxLayout()
        self.question_count_label = QLabel("Number of Questions:")
        self.question_count = QSpinBox()
        self.question_count.setMinimum(1)
        self.question_count.setMaximum(20)
        self.question_count.setValue(5)
        self.question_count_layout.addWidget(self.question_count_label)
        self.question_count_layout.addWidget(self.question_count)
        layout.addLayout(self.question_count_layout)
        
        self.generate_button = QPushButton("Generate Question Forms")
        self.generate_button.clicked.connect(self.generate_question_forms)
        layout.addWidget(self.generate_button)
        
        # Scroll area for questions
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.questions_layout = QVBoxLayout(self.scroll_content)
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll)
        
        self.save_button = QPushButton("Save Quiz")
        self.save_button.clicked.connect(self.save_quiz)
        self.save_button.setEnabled(False)
        layout.addWidget(self.save_button)
        
        self.setLayout(layout)
    
    def generate_question_forms(self):
        # Clear previous forms
        for i in reversed(range(self.questions_layout.count())):
            self.questions_layout.itemAt(i).widget().setParent(None)
        
        num_questions = self.question_count.value()
        
        for i in range(num_questions):
            question_group = QWidget()
            question_layout = QVBoxLayout(question_group)
            
            question_label = QLabel(f"Question {i+1}")
            question_label.setFont(QFont("Arial", 10, QFont.Bold))
            question_layout.addWidget(question_label)
            
            question_text = QLineEdit()
            question_text.setPlaceholderText("Enter question text")
            question_layout.addWidget(question_text)
            
            option_layout = QGridLayout()
            options = []
            
            # Create radio button group for correct answer
            radio_group = QButtonGroup(question_group)
            
            for j in range(4):
                radio = QRadioButton(f"Option {j+1}")
                radio.setChecked(j == 0)  # Default to first option being correct
                radio_group.addButton(radio, j)
                option_layout.addWidget(radio, j, 0)
                
                option_text = QLineEdit()
                option_text.setPlaceholderText(f"Enter option {j+1}")
                option_layout.addWidget(option_text, j, 1)
                options.append(option_text)
            
            question_layout.addLayout(option_layout)
            self.questions_layout.addWidget(question_group)
            
            # Store references to form elements
            question_data = {
                'text': question_text,
                'options': options,
                'correct_answer': radio_group
            }
            
            if i < len(self.questions):
                self.questions[i] = question_data
            else:
                self.questions.append(question_data)
        
        self.save_button.setEnabled(True)
    
    def save_quiz(self):
        title = self.quiz_title.text()
        
        if not title:
            QMessageBox.warning(self, "Error", "Please enter a quiz title")
            return
        
        # Validate all questions have content
        for i, q in enumerate(self.questions):
            if not q['text'].text():
                QMessageBox.warning(self, "Error", f"Question {i+1} is missing text")
                return
            
            for j, opt in enumerate(q['options']):
                if not opt.text():
                    QMessageBox.warning(self, "Error", f"Question {i+1}, Option {j+1} is missing text")
                    return
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Insert quiz
            cursor.execute("INSERT INTO quizzes (teacher_id, title) VALUES (?, ?)",
                          (self.teacher_id, title))
            quiz_id = cursor.lastrowid
            
            # Insert questions
            for i, q in enumerate(self.questions):
                question_text = q['text'].text()
                options = [opt.text() for opt in q['options']]
                correct_answer = q['correct_answer'].checkedId()
                
                cursor.execute(
                    "INSERT INTO questions (quiz_id, question_text, options, correct_answer) VALUES (?, ?, ?, ?)",
                    (quiz_id, question_text, json.dumps(options), correct_answer)
                )
            
            conn.commit()
            QMessageBox.information(self, "Success", "Quiz created successfully")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save quiz: {str(e)}")
        finally:
            conn.close()

class QuizWidget(QWidget):
    def __init__(self, user_id, user_role, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.user_role = user_role
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # Header
        self.header_label = QLabel("Available Quizzes")
        self.header_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.header_label)
        
        # Quiz list
        self.quiz_list = QListWidget()
        self.quiz_list.itemDoubleClicked.connect(self.on_quiz_selected)
        layout.addWidget(self.quiz_list)
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh Quizzes")
        self.refresh_button.clicked.connect(self.load_quizzes)
        layout.addWidget(self.refresh_button)
        
        self.setLayout(layout)
        self.load_quizzes()
    
    def load_quizzes(self):
        self.quiz_list.clear()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if self.user_role == "teacher":
            # Teachers see only their own quizzes
            cursor.execute("""
                SELECT q.id, q.title, COUNT(qu.id) 
                FROM quizzes q 
                LEFT JOIN questions qu ON q.id = qu.quiz_id 
                WHERE q.teacher_id = ? 
                GROUP BY q.id
            """, (self.user_id,))
        else:
            # Students see all quizzes
            cursor.execute("""
                SELECT q.id, q.title, COUNT(qu.id) 
                FROM quizzes q 
                LEFT JOIN questions qu ON q.id = qu.quiz_id 
                GROUP BY q.id
            """)
        
        quizzes = cursor.fetchall()
        conn.close()
        
        for quiz_id, title, question_count in quizzes:
            item = QListWidgetItem(f"{title} ({question_count} questions)")
            item.setData(Qt.UserRole, quiz_id)
            self.quiz_list.addItem(item)
    
    def on_quiz_selected(self, item):
        quiz_id = item.data(Qt.UserRole)
        
        if self.user_role == "teacher":
            # Teachers can view quiz details
            self.show_quiz_details(quiz_id)
        else:
            # Students can take the quiz
            self.take_quiz(quiz_id)
    
    def show_quiz_details(self, quiz_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT title FROM quizzes WHERE id = ?", (quiz_id,))
        quiz_title = cursor.fetchone()[0]
        
        cursor.execute("SELECT id, question_text, options, correct_answer FROM questions WHERE quiz_id = ?", (quiz_id,))
        questions = cursor.fetchall()
        
        conn.close()
        
        # Display quiz details in a new dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Quiz Details: {quiz_title}")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout()
        
        # Add quiz title
        title_label = QLabel(quiz_title)
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title_label)
        
        # Create scroll area for questions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        questions_layout = QVBoxLayout(scroll_content)
        
        for q_id, question_text, options_json, correct_answer in questions:
            options = json.loads(options_json)
            
            question_group = QWidget()
            q_layout = QVBoxLayout(question_group)
            
            q_layout.addWidget(QLabel(f"Question: {question_text}"))
            
            for i, option in enumerate(options):
                option_label = QLabel(f"{i}: {option}")
                if i == correct_answer:
                    option_label.setStyleSheet("color: green; font-weight: bold;")
                q_layout.addWidget(option_label)
            
            questions_layout.addWidget(question_group)
            questions_layout.addWidget(QLabel(""))  # Spacer
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def take_quiz(self, quiz_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT title FROM quizzes WHERE id = ?", (quiz_id,))
        quiz_title = cursor.fetchone()[0]
        
        cursor.execute("SELECT id, question_text, options, correct_answer FROM questions WHERE quiz_id = ?", (quiz_id,))
        questions = cursor.fetchall()
        
        conn.close()
        
        if not questions:
            QMessageBox.warning(self, "Error", "This quiz has no questions")
            return
        
        # Check if student has already taken this quiz
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM results WHERE student_id = ? AND quiz_id = ?", 
                      (self.user_id, quiz_id))
        existing_result = cursor.fetchone()
        conn.close()
        
        if existing_result:
            reply = QMessageBox.question(self, "Quiz Already Taken", 
                                        "You have already taken this quiz. Do you want to take it again?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        # Create quiz taking dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Taking Quiz: {quiz_title}")
        dialog.resize(600, 500)
        
        layout = QVBoxLayout()
        
        # Add quiz title
        title_label = QLabel(quiz_title)
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title_label)
        
        # Create scroll area for questions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        questions_layout = QVBoxLayout(scroll_content)
        
        # Track user answers
        user_answers = {}
        
        for q_id, question_text, options_json, correct_answer in questions:
            options = json.loads(options_json)
            
            question_group = QWidget()
            q_layout = QVBoxLayout(question_group)
            
            q_layout.addWidget(QLabel(f"Question: {question_text}"))
            
            # Create radio button group for answers
            radio_group = QButtonGroup(question_group)
            
            for i, option in enumerate(options):
                radio = QRadioButton(option)
                radio_group.addButton(radio, i)
                q_layout.addWidget(radio)
            
            questions_layout.addWidget(question_group)
            questions_layout.addWidget(QLabel(""))  # Spacer
            
            # Store the radio group for later retrieval of answers
            user_answers[q_id] = radio_group
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        submit_button = QPushButton("Submit Answers")
        submit_button.clicked.connect(lambda: self.submit_quiz_answers(dialog, quiz_id, questions, user_answers))
        layout.addWidget(submit_button)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def submit_quiz_answers(self, dialog, quiz_id, questions, user_answers):
        score = 0
        total_questions = len(questions)
        
        # Calculate score
        for q_id, question_text, options_json, correct_answer in questions:
            radio_group = user_answers[q_id]
            selected_answer = radio_group.checkedId()
            
            if selected_answer == correct_answer:
                score += 1
        
        # Save result to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO results (student_id, quiz_id, score, total_questions) VALUES (?, ?, ?, ?)",
            (self.user_id, quiz_id, score, total_questions)
        )
        
        conn.commit()
        conn.close()
        
        # Show result
        QMessageBox.information(dialog, "Quiz Result", 
                               f"Your score: {score}/{total_questions} ({score/total_questions*100:.1f}%)")
        
        dialog.accept()

class ResultsWidget(QWidget):
    def __init__(self, user_id, user_role, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.user_role = user_role
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # Header
        self.header_label = QLabel("Quiz Results")
        self.header_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.header_label)
        
        # Results list
        self.results_list = QListWidget()
        layout.addWidget(self.results_list)
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh Results")
        self.refresh_button.clicked.connect(self.load_results)
        layout.addWidget(self.refresh_button)
        
        self.setLayout(layout)
        self.load_results()
    
    def load_results(self):
        self.results_list.clear()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if self.user_role == "teacher":
            # Teachers see results for their quizzes
            cursor.execute("""
                SELECT r.id, u.username, q.title, r.score, r.total_questions
                FROM results r
                JOIN users u ON r.student_id = u.id
                JOIN quizzes q ON r.quiz_id = q.id
                WHERE q.teacher_id = ?
                ORDER BY q.title, u.username
            """, (self.user_id,))
        else:
            # Students see their own results
            cursor.execute("""
                SELECT r.id, u.username, q.title, r.score, r.total_questions
                FROM results r
                JOIN users u ON r.student_id = u.id
                JOIN quizzes q ON r.quiz_id = q.id
                WHERE r.student_id = ?
                ORDER BY r.id DESC
            """, (self.user_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        for result_id, username, quiz_title, score, total in results:
            percentage = (score / total) * 100 if total > 0 else 0
            item_text = f"{username}: {quiz_title} - {score}/{total} ({percentage:.1f}%)"
            item = QListWidgetItem(item_text)
            self.results_list.addItem(item)

class HomeWidget(QWidget):
    def __init__(self, username, user_role, parent=None):
        super().__init__(parent)
        self.username = username
        self.user_role = user_role
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # Welcome message
        welcome_label = QLabel(f"Welcome, {self.username}!")
        welcome_label.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(welcome_label)
        
        role_label = QLabel(f"You are logged in as: {self.user_role.capitalize()}")
        role_label.setFont(QFont("Arial", 12))
        layout.addWidget(role_label)
        
        # Instructions
        instructions = QLabel()
        if self.user_role == "teacher":
            instructions.setText(
                "As a teacher, you can:\n"
                "• Create new quizzes\n"
                "• View your existing quizzes\n"
                "• See student results"
            )
        else:
            instructions.setText(
                "As a student, you can:\n"
                "• Take quizzes\n"
                "• View your results"
            )
        instructions.setFont(QFont("Arial", 11))
        layout.addWidget(instructions)
        
        # App description
        description = QLabel(
            "Gesture-Based MCQ Solver is an educational application designed to make "
            "learning more interactive and engaging. Navigate through the sidebar "
            "to access different features of the application."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        
        layout.addStretch()
        self.setLayout(layout)

class SettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # Header
        self.header_label = QLabel("Settings")
        self.header_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.header_label)
        
        # Settings (placeholder)
        layout.addWidget(QLabel("Settings options will be implemented in future versions."))
        
        self.setLayout(layout)

class GestureMCQApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.user_id = None
        self.user_role = None
        self.username = None
        initialize_database()
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("Gesture-Based MCQ Solver")
        self.setGeometry(100, 100, 800, 600)
        
        # Create main layout with sidebar and content area
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        
        # Create sidebar
        self.sidebar = QListWidget()
        self.sidebar.setMaximumWidth(200)
        self.sidebar.setFont(QFont("Arial", 12))
        main_layout.addWidget(self.sidebar)
        
        # Create stacked widget for content
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        self.setCentralWidget(main_widget)
        
        # Show login dialog
        self.show_login_dialog()
    
    def show_login_dialog(self):
        login_dialog = LoginDialog(self)
        if login_dialog.exec() == QDialog.Accepted:
            self.setup_ui_after_login()
        else:
            # If login was canceled and we're not logged in, exit the app
            if not self.user_id:
                sys.exit()
    
    def setup_ui_after_login(self):
        # Clear sidebar and stacked widget
        self.sidebar.clear()
        for i in range(self.stacked_widget.count()):
            self.stacked_widget.removeWidget(self.stacked_widget.widget(0))
        
        # Add sidebar items
        self.sidebar.addItem("Home")
        self.sidebar.addItem("Quizzes")
        self.sidebar.addItem("Results")
        self.sidebar.addItem("Settings")
        
        if self.user_role == "teacher":
            self.sidebar.addItem("Create Quiz")
        
        self.sidebar.addItem("Sign Out")
        
        # Connect sidebar click event
        self.sidebar.currentRowChanged.connect(self.on_sidebar_change)
        
        # Add widgets to stacked widget
        self.home_widget = HomeWidget(self.username, self.user_role)
        self.stacked_widget.addWidget(self.home_widget)
        
        self.quiz_widget = QuizWidget(self.user_id, self.user_role)
        self.stacked_widget.addWidget(self.quiz_widget)
        
        self.results_widget = ResultsWidget(self.user_id, self.user_role)
        self.stacked_widget.addWidget(self.results_widget)
        
        self.settings_widget = SettingsWidget()
        self.stacked_widget.addWidget(self.settings_widget)
        
        if self.user_role == "teacher":
            self.create_quiz_widget = QWidget()
            create_layout = QVBoxLayout(self.create_quiz_widget)
            create_button = QPushButton("Create New Quiz")
            create_button.clicked.connect(self.on_create_quiz)
            create_layout.addWidget(create_button)
            create_layout.addStretch()
            self.stacked_widget.addWidget(self.create_quiz_widget)
        
        # Set default widget
        self.sidebar.setCurrentRow(0)
    
    def on_sidebar_change(self, index):
        if index < self.stacked_widget.count():
            if self.sidebar.item(index).text() == "Sign Out":
                self.sign_out()
            else:
                self.stacked_widget.setCurrentIndex(index)
    
    def on_create_quiz(self):
        dialog = CreateQuizDialog(self.user_id, self)
        if dialog.exec() == QDialog.Accepted:
            # Refresh quiz list after creating a new quiz
            self.quiz_widget.load_quizzes()
    
    def sign_out(self):
        self.user_id = None
        self.user_role = None
        self.username = None
        self.show_login_dialog()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GestureMCQApp()
    window.show()
    sys.exit(app.exec_())